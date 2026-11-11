#!/usr/bin/env python3
"""Build a release manifest from verified archived SNOMED capture evidence.

The archived cfg is parsed as scalar/provenance evidence, never supplied to the
renderer or staged as executable settings.  Git supplies the canonical engine.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re

import capture_archived_snomed as capture_tool
import execute_release_snomed as execution
import release_snomed


def _name_mappings(props):
    result = {}
    for key in sorted(props):
        if key.startswith('SCT.RELMAP.'):
            label, rela, inverse, relation = props[key].split('|')
            result[label] = {'rel': relation, 'rela': rela, 'inverse_rela': inverse}
    return result


def _targets(producer):
    old = re.findall(r'my\s*\(\s*\$ICDversion\s*\)\s*=\s*[\"\']([A-Za-z0-9_.-]+)[\"\']\s*;', producer)
    block = re.search(r'my\s*\(\s*\$ICDVSAB\s*\)\s*=.*?\bUNKNOWN[\"\']\s*;', producer, re.S)
    if len(old) != 1 or block is None: raise ValueError('Mapping target versions require unambiguous archived producer evidence')
    result = {'ICD9CM': 'ICD9CM_' + old[0]}
    for variable, rsab in [('i10id','ICD10'),('i10cmid','ICD10CM')]:
        value = re.findall(r'\(\s*\$refSetId\s+eq\s+\$' + variable + r'\s*\)\s*\?\s*[\"\']([^\"\']+)[\"\']', block[0])
        if len(value) != 1: raise ValueError('Archived producer target branch is ambiguous: ' + variable)
        full = value[0].replace('${ICDRSAB}', rsab)
        if not re.fullmatch(re.escape(rsab) + r'_[A-Za-z0-9_.-]+', full): raise ValueError('Unreviewed dynamic mapping target expression')
        result[rsab] = full
    return result


def _metadata_rows(text, width):
    rows, dialect = [], set()
    for line in text.splitlines():
        row = line.split('|')
        terminal = len(row) == width + 1 and row[-1] == ''
        if terminal: row = row[:-1]
        if len(row) != width: raise ValueError('Unexpected archived metadata wire width')
        rows.append(row); dialect.add(terminal)
    if not rows or len(dialect) != 1: raise ValueError('Mixed/empty metadata wire dialect requires review')
    return rows, {'terminal_delimiter': dialect.pop()}


def curate(captured, inventory, reference_receipt, engine_ref):
    if not re.fullmatch(r'[0-9a-f]{40}', engine_ref): raise ValueError('An immutable canonical source engine commit is required')
    if (captured.get('artifact_type') != 'archived-snomed-physical-capture' or
            captured.get('selected_payloads_inventory_verified') is not True or
            captured.get('expanded_files_created') is not False):
        raise ValueError('Verified read-only native capture is required')
    version = captured['version']; archive = captured['archive']; source = 'SNOMEDCT_US'
    if (inventory['version'] != version or inventory['archive_sha256'] != archive['sha256'] or
            inventory['archive_bytes'] != archive['bytes'] or
            reference_receipt['source'] != source or reference_receipt['version'] != version or
            reference_receipt['archive_sha256'] != archive['sha256'] or
            reference_receipt['archive_bytes'] != archive['bytes']):
        raise ValueError('Capture, inventory and frozen archive receipt identities differ')
    if reference_receipt.get('extracted') is not False or not reference_receipt.get('object_identity'):
        raise ValueError('The preserved archive needs the existing acquisition receipt/object identity')
    entries = {item['path']: item for item in inventory['entries']}
    small = captured['small_files']; cfg = capture_tool.properties(small['etc/sct.cfg']['text'])
    props = {key: capture_tool.expand(cfg,key) for key in cfg}
    if props['VSAB'] != version or props['RSAB'] != source or props['Release'] != 'Snapshot':
        raise ValueError('Archived configuration identity/view differs')
    source_rows, source_format = _metadata_rows(small['src/sources.src']['text'], 20)
    termgroups, termgroup_format = _metadata_rows(small['src/termgroups.src']['text'], 6)
    if len(source_rows) != 1 or len(source_rows[0]) != 20 or source_rows[0][0] != version:
        raise ValueError('Current source metadata must identify one complete source row')
    prior = {'source': source, 'version': source_rows[0][1]}
    if props['VSABOLD'] != prior['version']:
        raise ValueError('Archived metadata and previous-source cfg evidence require reconciliation')
    if any(len(row) != 6 or row[0] != version + '/' + row[5] for row in termgroups):
        raise ValueError('Saved termgroups do not identify current version/TTY rows')
    targets = _targets(small['bin/invert_rf2.pl']['text'])
    canonical = (Path(execution.__file__).resolve().parents[1] / execution.PACKAGE / 'bin/invert_rf2.pl').read_bytes()
    historical = canonical.replace(b"my($ICDversion) = $$CfgRef->getReqEle('MappingTarget.ICD9CM.Version');",
                                  ('my($ICDversion) = "' + targets['ICD9CM'].removeprefix('ICD9CM_') + '";').encode())
    for key in ('ICD10','ICD10CM'):
        historical = historical.replace(("$$CfgRef->getReqEle('MappingTarget."+key+"')").encode(),
                                        ('"${ICDRSAB}_'+targets[key].removeprefix(key+'_')+'"').encode())
    if historical != small['bin/invert_rf2.pl']['text'].encode():
        raise ValueError('Archived converter is outside the reviewed canonical producer family; inspect the code difference')
    cleanup = (Path(execution.__file__).resolve().parents[1] / execution.PACKAGE / 'bin/rmdanglingattrs.pl').read_bytes()
    if cleanup != small['bin/rmdanglingattrs.pl']['text'].encode():
        raise ValueError('Archived cleanup differs from the reviewed canonical producer family')
    capture_id = 'archive-sha256-' + archive['sha256']
    def descriptor(member, role):
        entry = entries.get(member)
        if not entry or entry['kind'] != 'file': raise ValueError('Required regular archived input is missing: ' + member)
        return {'role':role,'uri':Path(archive['path']).as_uri(),'sha256':entry['sha256'],'bytes':entry.get('size',entry.get('bytes')),
                'archive_member':member,'archive_format':'tar.gz','archive_sha256':archive['sha256'],'archive_bytes':archive['bytes']}
    def artifact(kind, name, data, files=None, artifact_source=source):
        return {'schema_version':1,'artifact_type':kind,'source':artifact_source,'version':name,
                'provenance':{'producer':'Preserved staff SNOMED inversion archive with physical RF2 capture',
                              'producer_version':small['bin/invert_rf2.pl']['sha256'],'capture_id':capture_id,'evidence_kind':'preserved'},
                'files':files or [],'data':data}
    native = captured['native']; observations = native['discovery']; mappings = {key:{} for key in release_snomed.CATEGORIES}; labels = {}
    names = _name_mappings(props)
    for category in ('relationship_types','association_refsets'):
        for identifier in observations[category]:
            observed_labels = native['type_fsn_labels'].get(identifier,[])
            matched = [(label,names[label]) for label in observed_labels if label in names]
            values = {json.dumps(value,sort_keys=True) for _,value in matched}
            if len(values) != 1: raise ValueError('Unresolved/conflicting physically observed native mapping: ' + identifier + ' ' + repr(observed_labels))
            labels[identifier] = sorted(label for label,_ in matched)[0]
            mappings[category][identifier] = {'decision':'represent',**matched[0][1]}
    for category,prefix,field in [('description_types','TTY.','tty'),('attribute_refsets','ATN.','atn'),
                                  ('concrete_types','ATN.','atn'),('refset_patterns','PATTERN.','pattern')]:
        for identifier in observations[category]:
            key = prefix + identifier
            if key not in props: raise ValueError('Physically observed native identifier lacks archived policy: ' + key)
            mappings[category][identifier] = {'decision':'represent',field:props[key]}
    for identifier in observations['map_correlations']:
        key = 'MAPINFO.' + identifier
        if key not in props: raise ValueError('Observed map correlation has no archived policy: ' + identifier)
        relation,rela = props[key].split('|');mappings['map_correlations'][identifier]={'decision':'represent','rel':relation,'rela':rela}
    date = execution._date(version); bounds={'start':int(props['SaidStart']),'end':int(props['SaidEnd']),
                                          'bound_kind':'reserved-historical-range','provenance_ref':'id-range'}
    if bounds['start']<=0 or bounds['end']<bounds['start']: raise ValueError('Invalid archived complete ID bounds')
    metadata_files = [descriptor(version+'/'+relative,role) for role,relative in execution.METADATA.items()
                      if role in ('sources-src','termgroups-src')]
    # ICD inventories are actually declared by the producer, not inferred from
    # their usual filenames. The fixed operational destinations remain stable.
    for legacy,role in [('ICD10META','icd10-target-inventory'),('ICD10CMMETA','icd10cm-target-inventory')]:
        member=posixpath.normpath(version+'/bin/'+props['File.INP.'+legacy])
        metadata_files.append(descriptor(member,role))
    package_path=posixpath.commonpath([posixpath.dirname(entry['path']) for entry in native['files'].values()])
    provider_prefix=version+'/orig/fromprovider/'
    if not package_path.startswith(provider_prefix):raise ValueError('Native package has no declared provider-relative root')
    package_name=package_path.removeprefix(provider_prefix).removesuffix('/Snapshot')
    native_files=[descriptor(entry['path'],role) for role,entry in sorted(native['files'].items())]
    for role,entry in native['files'].items():
        expected=next(value for value in native_files if value['role']==role)
        if (entry['sha256'],entry['bytes'])!=(expected['sha256'],expected['bytes']):raise ValueError('Native capture/inventory payload identity differs')
    attribute_prefix_proof=captured.get('enriched_attributes',{}).get('pre_enrichment_prefix',{})
    if (attribute_prefix_proof.get('prefix_equal') is not True or attribute_prefix_proof.get('complete_row_boundary') is not True or
            attribute_prefix_proof.get('suffix_non_semantic_type_or_source_rows') != 0):
        raise ValueError('attributes.orig requires a proved original-prefix/insertion-enrichment stage boundary')
    official=[]
    for relative,(width,_) in capture_tool.CORE.items():
        scope=captured['oracle_files'][relative]
        if set(map(int,scope['field_widths']))!={width} or set(scope['source_counts'])-{source,version,'SRC'}:
            raise ValueError('Official core file has unexpected source/version or field widths: '+relative)
        if relative=='src/attributes.orig' and any(key.startswith('E-') for key in scope['semantic_type_sources']):
            raise ValueError('Inversion attributes already contain insertion enrichment')
        role='src/attributes.src' if relative=='src/attributes.orig' else relative
        official.append(descriptor(version+'/'+relative,role))
    module_ids=set(native['active_modules']) | {row['target_module_id'] for row in native['module_dependencies']}
    artifacts={
        'publisher':artifact('publisher-bundle',version,{'edition':'US','rf2_view':'Snapshot','publisher_release_date':date.isoformat(),
            'package_name':package_name,'headers':native['headers'],'effective_time_bounds':native['effective_time_bounds'],
            'module_dependencies':native['module_dependencies'],'discovery':{**observations,'labels':labels}},native_files),
        'state':artifact('ncimeta-state','preserved-preparation-'+version,{'snapshot_id':capture_id,'sources_rows':source_rows,
            'termgroups_rows':termgroups,'target_inventories':['ICD10','ICD10CM'],
            'metadata_format':{'sources-src':source_format,'termgroups-src':termgroup_format},
            'scope':'Preserved preparation bytes; no historical database snapshot reconstruction is claimed'},metadata_files,'NCIMETA'),
        'policy':artifact('policy','preserved-policy-'+version,{'engine_ref':engine_ref,'supported_modules':sorted(module_ids),
            'mappings':mappings,'labels':labels,'mapping_targets':targets},
            [descriptor(version+'/'+path,'archived-'+Path(path).name) for path in ('etc/sct.cfg','bin/invert_rf2.pl','bin/rmdanglingattrs.pl')]),
        'source-plan':artifact('source-plan',version,{'replacement_baseline':prior,'comparison_baseline':None,'publisher_history':[],
            'mrdoc_required':False,'mapping_decisions':{key:{} for key in release_snomed.CATEGORIES},'label_decisions':{},
            'source_title':props[version+'.VSY.0']}),
        'id-range':artifact('id-allocation',version,{**{key:bounds[key] for key in ('start','end','bound_kind')},
            'kind':'captured-sct.cfg','production_reservation':False,'scope':'Historical isolated replay; not a new allocation'}),
        'environment':artifact('environment-profile','meme-dev-v1',{'profile_id':'meme-dev-v1'}),
        'validation':artifact('validation-profile','snomed-snapshot-core-v1',{'profile_id':'snomed-snapshot-core-v1'}),
        'official':artifact('reference-inversion',version,{'reference_stage':'inversion-src','attributes_original_prefix_proved':True},official)}
    config={'schema_version':2,'source':source,'version':version,'engine_ref':engine_ref,'policy_ref':'policy','environment_profile':'environment',
            'replacement_baseline':prior,'comparison_baseline':None,'publisher_history':[],
            'inputs':{'source_data':['publisher'],'source_data_stage':'publisher','reference_ncimeta':'state','identity_state':None,'source_plan':'source-plan'},
            'source_atom_ids':bounds,'validation_profile':'validation','output_stage':'inversion-src','source_options':{'rf2_view':'Snapshot'},
            'replay':{'reference_ref':'official','reference_stage':'inversion-src','comparison_profile':'exact'}}
    manifest={'schema_version':1,'artifact_type':'ncimeta-release-manifest','profile':release_snomed.PROFILE,'purpose':'historical-replay',
              'configuration':config,'artifacts':artifacts}
    findings=release_snomed.analyze(config,artifacts)
    if findings['issues']:raise ValueError('Curated source preflight has unresolved findings: '+json.dumps(findings['issues']))
    plan=execution.build_plan(config,artifacts)
    expected=execution.properties(base64.b64decode(plan['generated_files'][0]['data_b64']),True)
    # Representation catalogs may grow between releases. Check every physically
    # used mapping; unused extra table rows do not establish a data dependency.
    canonical_names=_name_mappings(expected)
    for category in ('relationship_types','association_refsets'):
        for identifier,mapping in mappings[category].items():
            candidates={json.dumps(canonical_names[label],sort_keys=True) for label in native['type_fsn_labels'][identifier] if label in canonical_names}
            if candidates!={json.dumps({key:mapping[key] for key in ('rel','rela','inverse_rela')},sort_keys=True)}:
                raise ValueError('Archived active relation mapping differs from reviewed canonical policy: '+identifier)
    for category,prefix,field in [('description_types','TTY.','tty'),('attribute_refsets','ATN.','atn'),('concrete_types','ATN.','atn'),('refset_patterns','PATTERN.','pattern')]:
        for identifier,mapping in mappings[category].items():
            if expected.get(prefix+identifier)!=mapping[field]:raise ValueError('Archived active metadata mapping differs from canonical policy: '+prefix+identifier)
    for identifier,mapping in mappings['map_correlations'].items():
        if expected.get('MAPINFO.'+identifier)!=mapping['rel']+'|'+mapping['rela']:raise ValueError('Archived active map policy differs from canonical policy')
    ignored={'ORIGDIR','REFDIR','Extension','RelCode','EngNumOld','File.INP.COMPLEXMAPS','File.INP.OldSubset','File.INP.URCid2Did','File.INP.STATEDRELS','LogLvl',
             'MappingTarget.ICD10','MappingTarget.ICD10CM','MappingTarget.ICD9CM.Version'}
    prefixes=('SCT.RELMAP.','TTY.','ATN.','PATTERN.','MAPINFO.')
    differences={key:{'archived':props.get(key),'generated':expected.get(key)} for key in set(props)|set(expected)
                 if key not in ignored and not key.startswith(prefixes) and props.get(key)!=expected.get(key)}
    if differences:raise ValueError('Non-derived legacy setting differences require review: '+json.dumps(differences,sort_keys=True))
    evidence={'schema_version':1,'status':'CURATED_ARCHIVED_SNOMED_MANIFEST','source':source,'version':version,
              'archive_sha256':archive['sha256'],'archive_bytes':archive['bytes'],'object_identity':reference_receipt['object_identity'],
              'source_cfg_sha256':small['etc/sct.cfg']['sha256'],'archived_producer_sha256':small['bin/invert_rf2.pl']['sha256'],
              'archived_cleanup_sha256':small['bin/rmdanglingattrs.pl']['sha256'],'mapping_targets_from_archived_literals':targets,
              'producer_byte_exact_after_target_bindings':True,'cleanup_byte_exact':True,
              'replacement_baseline_from_sources_row':prior,'source_atom_bounds_from_cfg':bounds,'native_roles':len(native_files),
              'native_payload_hashes_verified':True,'physical_observations':native['discovery'],'oracle_attributes_prefix_proof':attribute_prefix_proof,
              'preserved_metadata_consumed':True,'rendered_cfg_used_as_constructor':False,'archived_executable_seeded':False,
              'metadata_format':{'sources-src':source_format,'termgroups-src':termgroup_format},
              'unused_compatibility_settings_excluded_from_comparison':sorted(ignored),'active_policy_compatibility_verified':True,
              'native_execution_performed':False,'production_eligible':False}
    return manifest,evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--reference-receipt',type=Path,required=True);parser.add_argument('--engine-ref',required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--evidence-output',type=Path,required=True)
    args=parser.parse_args()
    manifest,evidence=curate(json.loads(args.capture.read_text()),json.loads(args.inventory.read_text()),json.loads(args.reference_receipt.read_text()),args.engine_ref)
    for path,value in [(args.output,manifest),(args.evidence_output,evidence)]:
        with path.open('x') as handle:json.dump(value,handle,indent=2);handle.write('\n')
    print(json.dumps({'manifest':str(args.output),'evidence':str(args.evidence_output),'version':manifest['configuration']['version']}))
