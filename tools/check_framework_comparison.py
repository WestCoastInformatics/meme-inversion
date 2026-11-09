#!/usr/bin/env python3
"""Check complete record comparison, saved roots and strict generated-ID proof."""
import copy
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile

import compare_framework_core as compare


def row(fields):return ('|'.join(map(str, fields)) + '\n').encode()


def attribute(identifier, atom, name, value):
    return row([identifier, atom, 'S', name, value, 'MDR_29_1', 'R', 'Y', 'N', 'N',
                'SRC_ATOM_ID', '', '', hashlib.md5(value.encode()).hexdigest(), ''])


def fixture():
    return {
        'classes_atoms.src': b''.join(row([value, 'MDR_29_1', 'MDR_29_1/PT', 'code'+str(value), 'R', 'Y', 'A', 'fixture', 'N', '', 'code'+str(value), '', 'ENG', '', '']) for value in (100, 101)),
        'attributes.src': attribute(1, 100, 'DEFINITION', 'native') + attribute(2, 100, 'CONTEXT', 'first') + attribute(3, 101, 'CONTEXT', 'second') + attribute(4, 100, 'SEMANTIC_TYPE', 'original'),
        'relationships.src': row([1, 'S', 100, 'BT', '', 101, 'MDR_29_1', 'MDR_29_1', 'R', 'Y', 'N', 'N', 'SRC_ATOM_ID', '', 'SRC_ATOM_ID', '', '', '', '']),
        'mergefacts.src': row([100, 'SY', 101, 'MDR_29_1', '', 'N', 'N', '', 'SRC_ATOM_ID', '', 'SRC_ATOM_ID', '', '']),
        'contexts.src': row([100, 'PAR', '', 99, 'MDR_29_1', 'MDR_29_1', '', '99', 'R', '', '', 100, 'SRC_ATOM_ID', '', 99, 'SRC_ATOM_ID', '', '']) + row([101, 'PAR', '', 100, 'MDR_29_1', 'MDR_29_1', '', '99.100', 'R', '', '', 101, 'SRC_ATOM_ID', '', 100, 'SRC_ATOM_ID', '', ''])}


def check():
    values = []
    with tempfile.TemporaryDirectory(prefix='framework-comparison-') as temporary:
        root = Path(temporary)
        def run(name, candidate, reference=None):
            reference = fixture() if reference is None else reference
            case = root/name;target=case/'MDR_29_1';(target/'src').mkdir(parents=True);out=case/'qa';out.mkdir()
            (target/'src/termgroups.src').write_bytes(b'MDR_29_1/PT|fixture\n')
            for filename, raw in candidate.items():(target/'src'/filename).write_bytes(raw)
            archive=case/'reference.tgz';entries=[]
            with tarfile.open(archive,'w:gz') as handle:
                for filename, raw in reference.items():
                    member='MDR_29_1/src/'+('attributes.orig' if filename=='attributes.src' else filename)
                    info=tarfile.TarInfo(member);info.size=len(raw);handle.addfile(info,io.BytesIO(raw))
                    entries.append({'path':member,'output_name':filename,'sha256':hashlib.sha256(raw).hexdigest(),'newline_count':raw.count(b'\n')})
            contract={'source':'MDR','version':'MDR_29_1','engine_ref':'36f1e10aeadb9faa184fd386573f82e6dd9b53c8','run_id':name,'root_atom_id':99,
                      'source_atom_ids':{'start':100,'end':200,'provenance_kind':'synthetic captured bounds','production_reservation_end_assessed':True},
                      'archive_path':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'reference_files':entries,'starting_stage':'publisher'}
            return compare.compare(contract,target,out,progress=lambda *args,**kwargs:None)
        result=run('exact',fixture())
        assert result['acceptance']['status']=='PASS_EXACT';values.append('All five exact files pass with independent validation')
        assert result['structure']['candidate']['external_root_atom_id']==99 and result['structure']['candidate']['checks_passed'];values.append('Only the saved external source root is accepted outside newly generated atoms')
        changed=fixture();changed['contexts.src']=b''.join(reversed(changed['contexts.src'].splitlines(keepends=True)))
        changed['attributes.src']=attribute(1,100,'DEFINITION','native')+attribute(2,101,'CONTEXT','second')+attribute(3,100,'CONTEXT','first')+attribute(4,100,'SEMANTIC_TYPE','original')
        result=run('context-order',changed)
        assert result['acceptance']['status']=='PASS_EQUIVALENT' and not result['acceptance']['all_five_exact'];values.append('Complete context rows and proved CONTEXT-only ID permutation are equivalent')
        assert result['files']['attributes.src']['attribute_diagnostics']['reference']['attribute_names']['SEMANTIC_TYPE']==1;values.append('Original semantic types remain in the core comparison')
        for name, mutate in [
            ('atom-content',lambda x:x.update({'classes_atoms.src':x['classes_atoms.src'].replace(b'fixture',b'changed',1)})),
            ('lost-duplicate',lambda x:x.update({'attributes.src':x['attributes.src']+attribute(5,100,'CONTEXT','first')})),
            ('non-context-id',lambda x:x.update({'attributes.src':x['attributes.src'].replace(b'1|100|S|DEFINITION',b'5|100|S|DEFINITION')})),
            ('qualifier',lambda x:x.update({'attributes.src':x['attributes.src'].replace(b'SRC_ATOM_ID|||',b'SRC_ATOM_ID|changed||',1)})),
            ('context-endpoint',lambda x:x.update({'contexts.src':x['contexts.src'].replace(b'|99|',b'|999|',1)}))]:
            changed=fixture();mutate(changed);result=run(name,changed)
            assert result['acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW',name
            values.append('Unreviewed change rejected: '+name)
        for name, mutate in [
            ('orphan',lambda x:x.update({'attributes.src':x['attributes.src'].replace(b'1|100|',b'1|999|',1)})),
            ('duplicate-aid',lambda x:x.update({'attributes.src':x['attributes.src'].replace(b'2|100|',b'1|100|',1)})),
            ('unknown-termgroup',lambda x:x.update({'classes_atoms.src':x['classes_atoms.src'].replace(b'/PT',b'/UNKNOWN',1)}))]:
            both=fixture();mutate(both);result=run(name,both,both)
            assert result['acceptance']['status']=='REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS',name
            values.append('Byte equality retains independent reference findings: '+name)
        reference=fixture();reference['relationships.src']=reference['relationships.src'].replace(b'SRC_ATOM_ID',b'SRC_ATTRIBUTE_ID',1)
        changed=copy.deepcopy(reference);changed['attributes.src']=attribute(1,100,'DEFINITION','native')+attribute(2,101,'CONTEXT','second')+attribute(3,100,'CONTEXT','first')+attribute(4,100,'SEMANTIC_TYPE','original')
        result=run('generated-reference',changed,reference)
        assert result['acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW' and not result['acceptance']['checks']['attribute_id_reference_safety'];values.append('Generated-ID references prevent attribute-ID equivalence')
    return values


if __name__=='__main__':
    values=check()
    for value in values:print('PASS',value)
    print(len(values),'framework comparison checks passed')
