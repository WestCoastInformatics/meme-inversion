#!/usr/bin/env python3
"""Confined NCIt discovery/decision fixtures; no conversion or external reads."""
from contextlib import contextmanager
import copy
import hashlib
import io
import json

import discover_release_nci as scanner
import nci_source_plan as plans


def fixture():
    version='NCI_2028_10A';prior={'source':'NCI','version':'NCI_2028_08B'}
    config={'schema_version':2,'source':'NCI','version':version,'engine_ref':'a'*40,
        'replacement_baseline':prior,'comparison_baseline':None,'publisher_history':[],
        'inputs':{'source_data':['publisher'],'source_data_stage':'publisher','reference_ncimeta':'state','identity_state':'root','source_plan':'plan'},
        'policy_ref':'policy','source_atom_ids':None,'source_options':{},'output_stage':'inversion-src'}
    source={key:'' for key in plans.SOURCE_FIELDS};source.update(source_name='NCI_{{release}}',low_source='NCI_{{replacement_release}}',restriction_level='0',normalized_source='NCI_{{release}}',stripped_source='NCI',version='{{release}}',source_family='NCI',official_name='NCIt',language='ENG')
    def group(tty):return dict(zip(plans.TERMGROUP_FIELDS,['NCI_{{release}}/'+tty,'NCI_{{replacement_release}}/'+tty,'N','N','N',tty]))
    model={'schema_version':1,'source':'NCI','sources':[source],'termgroups':[group('PT'),group('SY')],
        'publisher_termgroups':[['NCI','PT'],['NCI','SY']], 'publisher_properties':['P108','P90','P375'],
        'publisher_labels':{'P108':'Preferred_Name','P90':'FULL_SYN','P383':'Term Type','P384':'Term Source','R1':'isa'},'relationship_roles':['R1']}
    props={'VSAB':version,'RSAB':'NCI','CFG2RSAB':"'NCI'",'HC.RootNodeSaid':'91','HC.RootNodeCode':'V-NCI','HC.RootNodeName':'NCIt'}
    plan={'schema_version':1,'source':'NCI','version':version,'replacement_baseline':copy.deepcopy(prior),'comparison_baseline':None,'publisher_history':[],
          'new_subsources':[],'new_termgroups':[],'property_updates':{},'historical_exceptions':[]}
    def artifact(kind,ver,data):return {'schema_version':1,'artifact_type':kind,'source':'NCI','version':ver,'data':data,'files':[]}
    artifacts={'publisher':artifact('publisher-bundle',version,{}),'policy':artifact('policy',version,{'profile':plans.PROFILE,'metadata_model':model,'properties':props}),
               'plan':artifact('source-plan',version,plan),'state':artifact('ncimeta-state',version,{'profile':'nci-preserved-preparation-v1','replacement_baseline':copy.deepcopy(prior),'properties':copy.deepcopy(props)}),
               'root':artifact('identity-state',prior['version'],{'profile':'saved-hierarchy-root-v1','replacement_baseline':copy.deepcopy(prior),'root_atom_id':91,'root_code':'V-NCI','root_name':'NCIt'})}
    files={}
    def put(ref,role,raw):
        files[(ref,role)]=raw
        artifacts[ref]['files']=[x for x in artifacts[ref]['files'] if x['role']!=role]
        artifacts[ref]['files'].append({'role':role,'uri':'file:///fixture/'+role+'.txt','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    variables={'release':'2028_10A','replacement_release':'2028_08B'}
    def metadata(ref,role,rows,fields):put(ref,role,''.join('|'.join(plans.render(x[k],variables) for k in fields)+'|\n' for x in rows).encode())
    metadata('state','sources-src',model['sources'],plans.SOURCE_FIELDS);metadata('state','termgroups-src',model['termgroups'],plans.TERMGROUP_FIELDS)
    put('state','nci-configuration',''.join(k+' = '+v+'\n' for k,v in props.items()).encode())
    put('publisher','annotationDeclaration',b'P108|rdfs:label|Preferred_Name\nP90|rdfs:label|FULL_SYN\nP383|rdfs:label|Term Type\nP384|rdfs:label|Term Source\n')
    put('publisher','objectDeclaration',b'R1|rdfs:label|isa\n')
    put('publisher','classDeclaration',b'C1|P108|One\nC1|P90|Synonym|P383|SY|P384|NCI\n')
    put('publisher','relations',b'C1|relation|R1|C2\n');put('publisher','hierarchy',b'C1|C2\n')
    @contextmanager
    def open_role(ref,role):
        raw=files[(ref,role)];stream=io.BytesIO(raw)
        try:
            yield stream
            matches=[x for x in artifacts[ref]['files'] if x['role']==role]
            if len(matches)!=1 or matches[0]['sha256']!=hashlib.sha256(raw).hexdigest() or matches[0]['bytes']!=len(raw):raise ValueError('Confined verified reader rejected descriptor')
        finally:stream.close()
    return config,artifacts,files,put,metadata,open_role


def check():
    checks=[]
    def good(value,label):assert value,label;checks.append(label)
    def codes(report):return {x['code'] for x in report['issues']}
    def kinds(report):return {x['kind'] for x in report['decisions']}
    def run(change=None):
        c,a,f,p,m,o=fixture()
        if change:change(c,a,f,p,m)
        return scanner.analyze(c,a,o)
    c,a,f,p,m,o=fixture();original=copy.deepcopy((c,a,f));r=scanner.analyze(c,a,o)
    good(r['facts']['publisher_scan_complete'] and len(r['facts']['publisher_inputs'])==5,'all five publisher roles physically scanned with full hashes/counts')
    good(r['facts']['explicit_new_subsources']==[] and r['facts']['explicit_new_termgroups']==0 and kinds(r)=={'installed-state-review'},'explicit empty additions stay empty while installed-state scope remains honest')
    good(r['facts']['replacement_baseline']['version']=='NCI_2028_08B' and not r['facts']['calendar_predecessor_inferred'],'October explicitly uses inserted August without a guessed September')
    good(r['facts']['final_metadata_plan_validation'] is False and 'NCI_ALLOCATION_PENDING' in codes(r),'pre-allocation discovery invents no source atom range')
    good(not r['facts']['execution_authorized'] and not r['facts']['production_eligible'] and not r['facts']['installed_subsource_roots_and_ranks_authenticated'],'discovery never authenticates fresh roots/ranks or authorizes execution')
    good((c,a,f)==original and scanner.analyze(c,a,o)==r,'native data/request unchanged and report deterministic')
    def unknown(c,a,f,p,m):p('publisher','classDeclaration',f['publisher','classDeclaration']+b'C2|P90|Other|P383|PT|P384|NEW_SOURCE\n')
    x=run(unknown);good({'publisher-termgroup','subsource'}<=kinds(x),'new publisher source produces explicit mapping/metadata decisions')
    def new_tty(c,a,f,p,m):p('publisher','classDeclaration',f['publisher','classDeclaration']+b'C2|P90|Other|P383|NEWTTY|P384|NCI\n')
    x=run(new_tty);good({'publisher-termgroup','term-type-mapping'}<=kinds(x),'new native TTY is discovered before a producer could silently omit it')
    def add_tty(c,a,f,p,m):
        new_tty(c,a,f,p,m);plan=a['plan']['data'];entry=dict(zip(plans.TERMGROUP_FIELDS,['NCI_{{release}}/NEWTTY','NCI_{{release}}/SY','N','N','N','NEWTTY']))
        plan['property_updates']={'in2tty.NEWTTY':'NEWTTY'};plan['new_termgroups']=[{'metadata':entry,'after_termgroup':'NCI_{{release}}/SY','input_ttys':['NEWTTY']}]
        m('state','termgroups-src',a['policy']['data']['metadata_model']['termgroups']+[entry],plans.TERMGROUP_FIELDS)
    x=run(add_tty);good(kinds(x)=={'installed-state-review'} and x['facts']['explicit_new_termgroups']==1,'reviewed optional TTY addition covers discovery without requiring an allocation')
    def add_source(c,a,f,p,m):
        unknown(c,a,f,p,m);model=a['policy']['data']['metadata_model'];entry=copy.deepcopy(model['sources'][0]);entry.update(source_name='NEW_SOURCE_{{release}}',normalized_source='NEW_SOURCE_{{release}}',stripped_source='NEW_SOURCE',low_source='NCI_{{release}}',official_name='New source')
        group=dict(zip(plans.TERMGROUP_FIELDS,['NEW_SOURCE_{{release}}/PT','NCI_{{release}}/SY','N','N','N','PT']))
        a['plan']['data']['new_subsources']=[{'metadata':entry,'after_source':'NCI','publisher_names':['NEW_SOURCE'],'root':{'preferred_term':'New source','short_name':'NEW_SOURCE'}}]
        a['plan']['data']['new_termgroups']=[{'metadata':group,'after_termgroup':'NCI_{{release}}/SY','input_ttys':['PT']}]
        m('state','sources-src',model['sources']+[entry],plans.SOURCE_FIELDS);m('state','termgroups-src',model['termgroups']+[group],plans.TERMGROUP_FIELDS)
    x=run(add_source);good(kinds(x)=={'installed-state-review'} and x['facts']['explicit_new_subsources']==['NEW_SOURCE'],'reviewed optional subsource/root/termgroup decision covers its native alias')
    def duplicate_plan(c,a,f,p,m):add_tty(c,a,f,p,m);a['plan']['data']['new_termgroups']*=2
    good('NCI_REPRESENTATION_PLAN_INVALID' in codes(run(duplicate_plan)),'duplicate optional additions fail before readiness')
    def cyclic(c,a,f,p,m):add_source(c,a,f,p,m);a['plan']['data']['new_subsources'][0]['metadata']['low_source']='NEW_SOURCE_{{release}}'
    good('NCI_REPRESENTATION_PLAN_INVALID' in codes(run(cyclic)),'cyclic source rankings rejected before allocation')
    def changed_label(c,a,f,p,m):p('publisher','annotationDeclaration',f['publisher','annotationDeclaration'].replace(b'Term Type',b'Different Type'))
    good('publisher-label' in kinds(run(changed_label)),'qualifier label change cannot hide behind unchanged P90 field codes')
    def role_change(c,a,f,p,m):p('publisher','relations',b'C1|relation|R9|C2\n')
    good('relationship-role' in kinds(run(role_change)),'new relationship role requires a representation decision')
    def property_change(c,a,f,p,m):p('publisher','classDeclaration',f['publisher','classDeclaration']+b'C1|P999|Unknown\n')
    good('publisher-property' in kinds(run(property_change)),'new publisher property is reported explicitly')
    def missing_mapping(c,a,f,p,m):
        add_source(c,a,f,p,m);a['plan']['data']['new_subsources']=[];a['plan']['data']['new_termgroups']=[]
        model=a['policy']['data']['metadata_model'];model['publisher_termgroups'].append(['NEW_SOURCE','PT'])
    good('subsource' in kinds(run(missing_mapping)),'catalogued source/TTY without mapping does not become accepted')
    def missing_group(c,a,f,p,m):
        add_tty(c,a,f,p,m);m('state','termgroups-src',a['policy']['data']['metadata_model']['termgroups'],plans.TERMGROUP_FIELDS)
    good('termgroup-metadata' in kinds(run(missing_group)),'output type with reviewed mapping still needs its physical metadata role')
    def missing_role(c,a,f,p,m):a['publisher']['files']=[x for x in a['publisher']['files'] if x['role']!='hierarchy']
    x=run(missing_role);good(not x['facts']['publisher_scan_complete'] and 'NCI_INPUT_ROLE_REQUIRED' in codes(x),'missing publisher role yields useful partial discovery, never complete coverage')
    def duplicate_role(c,a,f,p,m):a['publisher']['files'].append(copy.deepcopy(a['publisher']['files'][0]))
    good('NCI_INPUT_ROLE_REQUIRED' in codes(run(duplicate_role)),'duplicate file role cannot select arbitrary bytes')
    def conflict(c,a,f,p,m):p('publisher','objectDeclaration',f['publisher','objectDeclaration']+b'R1|rdfs:label|different\n')
    good('NCI_PUBLISHER_INPUT_INVALID' in codes(run(conflict)),'conflicting duplicate property label is a physical discovery error')
    def bad_shape(c,a,f,p,m):p('publisher','classDeclaration',b'C1|P90|Synonym|P384|NCI|P383|SY\n')
    good('NCI_PUBLISHER_INPUT_INVALID' in codes(run(bad_shape)),'unreviewed synonym qualifier order rejected')
    def bad_newline(c,a,f,p,m):p('publisher','hierarchy',b'C1|C2')
    good('NCI_PUBLISHER_INPUT_INVALID' in codes(run(bad_newline)),'unterminated publisher role rejected')
    def bad_utf8(c,a,f,p,m):p('publisher','hierarchy',b'C1|\xff\n')
    good('NCI_PUBLISHER_INPUT_INVALID' in codes(run(bad_utf8)),'invalid publisher UTF-8 rejected')
    def changed_bytes(c,a,f,p,m):f['publisher','hierarchy']=b'C1|C3\n'
    x=run(changed_bytes);good('NCI_PUBLISHER_INPUT_INVALID' in codes(x) and not x['facts']['publisher_scan_complete'],'physical/hash disagreement cannot establish complete native coverage')
    def missing_root(c,a,f,p,m):a.pop('root')
    good('NCI_ARTIFACT_REQUIRED' in codes(run(missing_root)),'absent saved root reported while publisher discovery continues')
    def wrong_root_prior(c,a,f,p,m):a['root']['data']['replacement_baseline']['version']='NCI_2028_09A'
    good('NCI_ROOT_STATE_INVALID' in codes(run(wrong_root_prior)),'root from a calendar month cannot substitute for actual inserted predecessor')
    def wrong_state_prior(c,a,f,p,m):a['state']['data']['replacement_baseline']['version']='NCI_2028_09A'
    good('NCI_STATE_BASELINE_MISMATCH' in codes(run(wrong_state_prior)),'preserved ranking metadata must bind the explicit predecessor')
    def root_mismatch(c,a,f,p,m):p('state','nci-configuration',f['state','nci-configuration'].replace(b' = 91',b' = 92'))
    good({'NCI_ROOT_CONFIGURATION_MISMATCH','NCI_STATE_PROPERTIES_MISMATCH'}<=codes(run(root_mismatch)),'physical root/configuration contradiction remains a blocker')
    def fresh_state(c,a,f,p,m):a['state']['data']={'profile':'ncimeta-state-v2','capture_id':'declared-only'}
    good('NCI_FRESH_STATE_UNVERIFIED' in codes(run(fresh_state)),'declared fresh state cannot approve its own exporter/coherence')
    def repeated(c,a,f,p,m):p('publisher','classDeclaration',b'C1|P90|Alias|P383|SY|P384|NCI\n'*100)
    x=run(repeated);good(x['facts']['observed_publisher_termgroups']==[{'publisher_source':'NCI','input_tty':'SY','occurrences':100}],'every observed occurrence counted without retaining all native rows')
    def bounded(c,a,f,p,m):c['source_atom_ids']={'start':100,'end':10000}
    x=run(bounded);good(x['facts']['final_metadata_plan_validation'] is True,'complete reviewed allocation reuses existing generator validation unchanged')
    def historical(c,a,f,p,m):c['replay']={'reference_ref':'reference'}
    x=run(historical);good(kinds(x)==set() and 'NCI_PRESERVED_STATE_SCOPE' in codes(x),'historical representation discovery remains separate from fresh operational state proof')
    def crlf(c,a,f,p,m):p('publisher','hierarchy',b'C1|C2\r\n')
    good(run(crlf)['facts']['publisher_scan_complete'],'native CRLF input is supported without changing its verified bytes')
    def embedded_cr(c,a,f,p,m):p('publisher','hierarchy',b'C1|C\r2\n')
    good('NCI_PUBLISHER_INPUT_INVALID' in codes(run(embedded_cr)),'uncharacterized embedded carriage return is rejected')
    def oversized(c,a,f,p,m):p('publisher','hierarchy',b'C1|'+b'x'*scanner.MAX_LINE_BYTES+b'\n')
    good('NCI_PUBLISHER_INPUT_INVALID' in codes(run(oversized)),'oversized lines are read with an explicit bound and rejected')
    saved=scanner.MAX_VOCABULARY_BYTES;scanner.MAX_VOCABULARY_BYTES=5
    try:good('NCI_PUBLISHER_INPUT_INVALID' in codes(run()),'total retained vocabulary text is bounded independently of record count')
    finally:scanner.MAX_VOCABULARY_BYTES=saved
    def token_collision(c,a,f,p,m):a['policy']['data']['metadata_model']['publisher_termgroups'].append(['NC','IPT'])
    good('ambiguous-native-token' in kinds(run(token_collision)),'ambiguous concatenated native source/TTY tokens require review')
    def missing_publisher_with_exception(c,a,f,p,m):
        a['plan']['data']['historical_exceptions']=[{'kind':'unmapped-publisher-source','identifier':'KNOWN','reason':'Captured historical finding','version':c['version'],'native_sha256':{}}]
        a.pop('publisher')
    x=run(missing_publisher_with_exception)
    good('NCI_ARTIFACT_REQUIRED' in codes(x) and not x['facts']['retained_historical_exceptions'][0]['exact_native_hashes_match'],'missing publisher with historical findings returns partial report without false hash binding')
    def bad_exceptions(c,a,f,p,m):a['plan']['data']['historical_exceptions']={'wrong':'shape'}
    good('NCI_REPRESENTATION_PLAN_INVALID' in codes(run(bad_exceptions)),'malformed exception declaration remains a structured blocker')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
