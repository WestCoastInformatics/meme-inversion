#!/usr/bin/env python3
"""Independent golden-property, plan-binding and real Perl preparation fixtures."""
import base64,copy,hashlib,json,subprocess,tempfile
from pathlib import Path
import nci_configuration as nci

ROOT=Path(__file__).resolve().parents[1]

def fixture():
 case=json.loads((ROOT/'docs/inversion-review/case-catalog/nci-stable-context-order.json').read_text());config=copy.deepcopy(case['configuration']);artifacts=copy.deepcopy(case['artifacts']);config['engine_ref']='a'*40
 def put(role,value):
  ref='sha256:'+nci.digest(value);artifacts[ref]={'role':role,'value':value};return ref
 raw=(ROOT/'engines/nci/nci.cfg.in').read_bytes();template={'repository_path':'engines/nci/nci.cfg.in','sha256':nci.sha(raw),'data_b64':base64.b64encode(raw).decode()}
 config['policy_ref']=put('nci-representation-policy',{'profile':nci.PROFILE,'engine_ref':config['engine_ref'],'template_repository_path':template['repository_path'],'template_sha256':template['sha256']})
 config['inputs']['identity_state']=put('saved-hierarchy-root',{'root_atom_id':31926003,'root_code':'V-NCI','root_name':'National Cancer Institute Thesaurus'})
 config['source_atom_ids']['bound_kind']='historical-emitted-range';config['source_atom_ids']['provenance_ref']=put('isolated-historical-ID-range',{'start':config['source_atom_ids']['start'],'end':config['source_atom_ids']['end'],'production_reservation':False})
 metadata=[{'path':config['version']+'/src/'+name,'sha256':nci.sha(data)} for name,data in [('sources.src',b'NCI_2026_10D|NCI_2026_08E|0\n'),('termgroups.src',b'NCI/PT|NCI_2026_10D\n')]]
 config['inputs']['reference_ncimeta']=put('preserved-reference-metadata',metadata)
 legacy=copy.deepcopy(case['legacy_case']);legacy['archived_metadata_inputs']=metadata
 return config,artifacts,template,legacy,put

def check():
 passed=[]
 def good(value,label):assert value,label;passed.append(label)
 def reject(action,label):
  try:action()
  except (ValueError,KeyError):passed.append(label)
  else:raise AssertionError(label)
 config,artifacts,template,legacy,put=fixture();recipe=nci.generate(config,artifacts,template);raw=base64.b64decode(recipe['files'][0]['data_b64'])
 old=subprocess.check_output(['git','-C',str(ROOT),'show','bfda2ce9b0d0ab23db3182d37aab4b1f5a13fd09:sources/NCI_2026_10D/etc/nci.cfg'])
 # The captured deployed properties are the independent golden fixture.
 good(nci.properties(raw)==nci.properties(old),'Every generated October property equals the captured stable producer settings')
 good(recipe['bindings']['replacement_baseline']['version']=='NCI_2026_08E','October explicitly replaces August without requiring September')
 good(recipe['preparation_arguments']['role-groups']==['../orig/fromprovider/relations-20261026.txt'],'Native filenames come from the frozen export manifest')
 lock={'configuration':config,'case':{'artifacts':artifacts,'legacy_case':legacy,'configuration_generation':{'profile':nci.PROFILE,'repository_path':template['repository_path'],'sha256':template['sha256']}},'configuration_generation':recipe}
 good(nci.from_lock(lock)==recipe,'Recipe round trip binds common configuration, metadata, legacy inputs and template')
 for label,mutate in [
  ('same-version baseline',lambda c:c['replacement_baseline'].update(version=c['version'])),
  ('future baseline',lambda c:c['replacement_baseline'].update(version='NCI_2027_01A')),
  ('implicit baseline',lambda c:c.update(replacement_baseline=None)),
  ('invalid release month',lambda c:c.update(version='NCI_2026_13A')),
  ('wrong language option',lambda c:c['source_options'].update(language='ENG')),
  ('reversed ID bounds',lambda c:c['source_atom_ids'].update(end=1)),
  ('boolean ID bound',lambda c:c['source_atom_ids'].update(start=True)),
  ('changed ID evidence',lambda c:c['source_atom_ids'].update(end=c['source_atom_ids']['end']+1)),
  ('production reservation relabeling',lambda c:c['source_atom_ids'].update(bound_kind='reserved-historical-range')),
  ('changed explicit transition',lambda c:c['replacement_baseline'].update(version='NCI_2026_09D')),
  ('unsupported history stage',lambda c:c['publisher_history'].append('unexpected')),
  ('unsupported comparison stage',lambda c:c.update(comparison_baseline={'source':'NCI','version':'NCI_2026_09D'})),
  ('unresolved engine',lambda c:c.update(engine_ref='HEAD')),
 ]:
  bad=copy.deepcopy(config);mutate(bad);reject(lambda:nci.generate(bad,artifacts,template),'Reject '+label)
 for label,change in [('changed payload',lambda t:t.update(data_b64=base64.b64encode(b'changed').decode())),('wrong package path',lambda t:t.update(repository_path='sources/old/nci.cfg.in'))]:
  bad=copy.deepcopy(template);change(bad);reject(lambda:nci.generate(config,artifacts,bad),'Reject '+label)
 for label,change in [('modified recipe',lambda x:x['configuration_generation']['files'][0].update(sha256='0'*64)),('changed legacy inputs',lambda x:x['case']['legacy_case']['native_inputs'].pop()),('missing recipe',lambda x:x.pop('configuration_generation'))]:
  bad=copy.deepcopy(lock);change(bad);reject(lambda:nci.from_lock(bad),'Reject '+label)
 for label,mutation in [('missing role',lambda x:x.pop()),('duplicate role',lambda x:x.append(x[0].copy())),('unsafe path',lambda x:x[0].update(path='NCI_2026_10D/orig/fromprovider/../../annotationDeclaration-20261026.txt'))]:
  c,a,t,l,put=fixture();values=copy.deepcopy(a[c['inputs']['source_data'][0]]['value']);mutation(values);c['inputs']['source_data']=[put('source-data',values)];reject(lambda:nci.generate(c,a,t),'Reject '+label)
 # A later plan reuses the same code/policy without assuming adjacency or deriving publisher filenames.
 c,a,t,l,put=fixture();c['version']='NCI_2027_02B';c['replacement_baseline']={'source':'NCI','version':'NCI_2026_12C'}
 plan=copy.deepcopy(a[c['inputs']['source_plan']]['value']);plan['replacement_baseline']=c['replacement_baseline'];c['inputs']['source_plan']=put('reviewed-historical-transition',plan)
 native=copy.deepcopy(a[c['inputs']['source_data'][0]]['value'])
 for item in native:item['path']=item['path'].replace('NCI_2026_10D','NCI_2027_02B').replace('20261026','20270303')
 c['inputs']['source_data']=[put('source-data',native)];meta=copy.deepcopy(a[c['inputs']['reference_ncimeta']]['value'])
 for item in meta:item['path']=item['path'].replace('NCI_2026_10D','NCI_2027_02B')
 c['inputs']['reference_ncimeta']=put('preserved-reference-metadata',meta);future=nci.generate(c,a,t);props=nci.properties(base64.b64decode(future['files'][0]['data_b64']))
 good(props['VSAB']=='NCI_2027_02B' and props['vsab.FDA']=='FDA_2027_02B' and 'FDA_2027_02B.RSSN' in props,'Future synthetic plan generates versioned source/subsource properties from the same policy')
 good(future['preparation_arguments']['role-groups']==['../orig/fromprovider/relations-20270303.txt'],'Export date is independently declared, not derived from release month')
 with tempfile.TemporaryDirectory(prefix='nci-generation-') as temporary:
  target=Path(temporary);(target/'src').mkdir();(target/'etc').mkdir();(target/'src/sources.src').write_bytes(b'NCI_2026_10D|NCI_2026_08E|0\n');(target/'src/termgroups.src').write_bytes(b'NCI/PT|NCI_2026_10D\n');(target/'etc/nci.cfg').write_bytes(raw);(target/'etc/nci.cfg').chmod(0o444)
  nci.verify_metadata(recipe,target);nci.verify_files(recipe,target);passed.append('Saved metadata and read-only generated file verify before execution')
  (target/'etc/nci.cfg').chmod(0o644);reject(lambda:nci.verify_files(recipe,target),'Writable generated configuration rejected');(target/'etc/nci.cfg').chmod(0o444)
  (target/'src/sources.src').write_bytes(b'NCI_2026_10D|NCI_2026_09D|0\n');reject(lambda:nci.verify_metadata(recipe,target),'Changed source metadata rejected')
  # Even a freshly hash-bound metadata artifact cannot silently change the agreed replacement.
  bad=copy.deepcopy(recipe);bad['bindings']['metadata_inputs'][0]['sha256']=nci.sha((target/'src/sources.src').read_bytes());reject(lambda:nci.verify_metadata(bad,target),'Metadata/plan baseline disagreement rejected independently of file hashing')
 with tempfile.TemporaryDirectory(prefix='nci-native-argv-') as temporary:
  target=Path(temporary);(target/'bin').mkdir();(target/'orig').mkdir();(target/'tmp').mkdir();native=target/'orig/fromprovider';native.mkdir()
  values={'annotationDeclaration':'R1|rdfs:label|role1\nP9|rdfs:label|custom\n','objectDeclaration':'','classDeclaration':'C1|P108|Alpha\nC1|P9|value\n','relations':'C1||R1|C2\n','hierarchy':'C2|C1\n'}
  paths=[]
  for role in nci.ROLES:p=native/(role+'-20401231.txt');p.write_text(values[role]);paths.append(str(p))
  (target/'orig/rels_needing_relgrp.txt').write_text('')
  script=ROOT/'engines/nci/bin/create_tref.pl';run=subprocess.run(['/usr/bin/perl',str(script),*paths],cwd=target/'bin',capture_output=True,text=True)
  good(run.returncode==0 and (target/'tmp/MRCONSO.TREF.tmp').read_text()=='|Alpha|C1||NCIPT||\n' and (target/'tmp/MRSAT.TREF.tmp').read_text()=='|C1|CUI|custom|value|\n' and (target/'tmp/MRREL.TREF.tmp').read_text()=='1|C2|CUI||RO|role1|C1|CUI|\n|C1|CUI||CHD|isa|C2|CUI|\n','Real TREF producer accepts independently dated inputs and retains golden serialization')
  run=subprocess.run(['/usr/bin/perl',str(script)],cwd=target/'bin',capture_output=True);good(run.returncode!=0,'TREF producer rejects missing plan arguments instead of a dated fallback')
  Path(paths[3]).write_text('C1|1|R1|C2\nC1|1|R2|C3\nC2||R1|C3\n');script=ROOT/'engines/nci/bin/create_rolegroups.pl';run=subprocess.run(['/usr/bin/perl',str(script),paths[3]],cwd=target/'bin',capture_output=True)
  good(run.returncode==0 and (target/'tmp/rolegroups.tmp').read_text()=='C1|1\nC1|1\n','Real role-group producer uses declared input with unchanged serialization')
  run=subprocess.run(['/usr/bin/perl',str(script)],cwd=target/'bin',capture_output=True);good(run.returncode!=0,'Role-group producer rejects missing plan input')
 for name in ['invert_NCI.pl','delete_dup_tref_lines.pl']:
  original=subprocess.check_output(['git','-C',str(ROOT),'show','bfda2ce:sources/NCI_2026_10D/bin/'+name]);frozen=subprocess.check_output(['git','-C',str(ROOT),'show','2a22938:engines/nci/bin/'+name]);good(frozen==original,'Historical v1 core policy bytes unchanged: '+name)
 return passed
if __name__=='__main__':
 values=check()
 for item in values:print('PASS',item)
 print(len(values),'NCIt configuration generation checks passed')
