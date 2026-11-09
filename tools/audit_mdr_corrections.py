#!/usr/bin/env python3
"""Predict corrected MDR attributes from native history and archived records."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile

from compare_framework_core import file_info

EXPECTED_COUNTS=(27,189520,937523)


def audit(package,target,run,raw):
    if package['source']!='MDR' or package.get('case_variant')!='consistent-history-context':raise RuntimeError('Unreviewed MDR correction profile')
    files=raw['comparison']['files']
    for name in ['classes_atoms.src','relationships.src','mergefacts.src']:
        if not files[name]['exact_match']:raise RuntimeError('Unrelated core output changed: '+name)
    if not files['contexts.src']['row_multiset']['equal_preserving_multiplicity']:raise RuntimeError('Hierarchy records changed')
    if not raw['comparison']['structure']['candidate']['checks_passed']:raise RuntimeError('Corrected candidate validation failed')
    if not files['attributes.src']['attribute_diagnostics']['positive_unique_ids']:raise RuntimeError('Attribute IDs must be positive and unique')
    atoms={};eligible=set();roots={};relationship_ids=set()
    with (target/'src/classes_atoms.src').open('rb') as handle:
        for line in handle:
            fields=line.removesuffix(b'\n').split(b'|');atoms[fields[0]]=fields
            if fields[2] in [b'MDR_29_1/PT',b'MDR_29_1/LLT',b'MDR_29_1/OL']:eligible.add(fields[3])
            if fields[2]==b'MDR_29_1/OS':roots[fields[0]]=fields[7]+b'^'
    if len(roots)!=EXPECTED_COUNTS[0]:raise RuntimeError('Unexpected native SOC/root contract')
    with (target/'src/relationships.src').open('rb') as handle:
        for line in handle:
            identifier=line.split(b'|',1)[0]
            if identifier in relationship_ids:raise RuntimeError('Duplicate relationship ID')
            relationship_ids.add(identifier)
    expected=hashlib.sha256();ordinary=contexts=history=reference_bad_history=changed_sibling_lists=0
    native_history=iter((target/'orig/mdr_by_version.txt').open('rb'));context_rows=[];context_ids=[];phase='ordinary';last_id=0;reference_digest=hashlib.sha256()
    def emit(fields):
        nonlocal last_id
        identifier=int(fields[0])
        if identifier!=last_id+1:raise RuntimeError('Predicted attribute allocation is not contiguous')
        last_id=identifier;expected.update(b'|'.join(fields)+b'\n')
    def emit_contexts():
        nonlocal contexts,changed_sibling_lists
        if not context_rows or context_ids!=list(range(context_ids[0],context_ids[-1]+1)):raise RuntimeError('Archived context block has unexpected IDs')
        root_id=str(package['root_atom_id']).encode()
        rows=sorted(context_rows,key=lambda row:(row[1]!=root_id,row[1]))
        # Python's stable sort retains each node's native path sequence.
        for identifier,row in zip(context_ids,rows):
            fields=row.copy();fields[0]=str(identifier).encode()
            if fields[1] in roots:
                parts=fields[4].split(b'\t')
                if len(parts)!=6:raise RuntimeError('Unexpected root CONTEXT layout')
                names=[roots[key] for key in sorted(roots) if key!=fields[1]]
                if sorted(parts[5].split(b'~'))!=sorted(names):raise RuntimeError('Archived sibling names disagree with native atoms')
                value=b'~'.join(names);changed_sibling_lists+=parts[5]!=value;parts[5]=value
                fields[4]=b'\t'.join(parts);fields[13]=hashlib.md5(fields[4]).hexdigest().encode()
            emit(fields);contexts+=1
    with tarfile.open(package['archive_path'],'r|gz') as archive:
        for member in archive:
            if member.name!='MDR_29_1/src/attributes.orig':continue
            if not member.isfile():raise RuntimeError('Official attributes are not a regular file')
            for line in archive.extractfile(member):
                reference_digest.update(line);fields=line.removesuffix(b'\n').split(b'|')
                if len(fields)!=15:raise RuntimeError('Malformed archived attribute')
                if fields[3]==b'CONTEXT':
                    if phase=='history':raise RuntimeError('Unexpected context after history')
                    phase='context';context_rows.append(fields);context_ids.append(int(fields[0]));continue
                if fields[3]==b'PT_IN_VERSION':
                    if phase=='context':emit_contexts()
                    phase='history';native=next(native_history,None)
                    if native is None:raise RuntimeError('Archived history exceeds native input')
                    clean=native[:-2] if native.endswith(b'\r\n') else native[:-1] if native.endswith(b'\n') else native
                    if b'\r' in clean:raise RuntimeError('Unexpected history control character')
                    native_fields=clean.split(b'|')
                    if len(native_fields)!=2 or native_fields[0] not in eligible:raise RuntimeError('Unexpected native history code/shape')
                    code,value=native_fields
                    predicted=[fields[0],code,b'S',b'PT_IN_VERSION',value,b'MDR_29_1',b'R',b'Y',b'N',b'N',b'CODE_SOURCE',b'MDR_29_1',b'',hashlib.md5(value).hexdigest().encode(),b'']
                    if fields[:13]+fields[14:]!=predicted[:13]+predicted[14:]:raise RuntimeError('History fields differ beyond the reviewed digest correction')
                    if fields[13]!=hashlib.md5(value+b'\r').hexdigest().encode():raise RuntimeError('Archived digest discrepancy is not the characterized CR issue')
                    reference_bad_history+=fields[13]!=predicted[13];emit(predicted);history+=1
                else:
                    if phase!='ordinary':raise RuntimeError('Unexpected ordinary attribute after context/history')
                    emit(fields);ordinary+=1
    if next(native_history,None) is not None:raise RuntimeError('Unconsumed native history')
    native_history.close()
    if reference_digest.hexdigest()!=files['attributes.src']['reference']['sha256']:raise RuntimeError('Official attribute reference changed')
    if (contexts,history,reference_bad_history)!=(EXPECTED_COUNTS[1],EXPECTED_COUNTS[2],EXPECTED_COUNTS[2]):raise RuntimeError('Correction population differs from the reviewed case')
    if expected.hexdigest()!=files['attributes.src']['candidate']['sha256']:raise RuntimeError('Fresh attributes differ from independently predicted complete records/IDs')
    rel_references=0
    with (target/'src/attributes.src').open('rb') as handle:
        for line in handle:
            fields=line.removesuffix(b'\n').split(b'|')
            if b'\r' in line:raise RuntimeError('Carriage return remains in generated attributes')
            if fields[10]==b'SRC_REL_ID':
                if fields[1] not in relationship_ids or fields[11]!=b'MDR_29_1':raise RuntimeError('Unresolved source relationship attribute reference')
                rel_references+=1
    for name,item in files.items():
        if file_info(target/'src'/name)!=item['candidate']:raise RuntimeError('Candidate changed during audit')
    return {'status':'PASS_REVIEWED_CORRECTIONS','run_id':package['run_id'],'engine_ref':package['engine_ref'],'runtime_ref':package['runtime_ref'],
            'expected_attribute_sha256':expected.hexdigest(),'ordinary_attributes_unchanged':ordinary,'context_attributes_predicted_with_exact_ids':contexts,
            'sibling_lists_reordered_to_stable_root_id_order':changed_sibling_lists,'history_attributes_predicted_from_preserved_native_input':history,
            'archived_history_digest_findings_explained':reference_bad_history,'resolved_source_relationship_attribute_references':rel_references,
            'ignored_fields':[],'output_rewritten':False,'production_eligible':False,
            'scope':'All five core outputs; exact predicted corrected attributes including generated IDs; raw official comparison retained. Repeatability requires separately recorded full runs.'}
