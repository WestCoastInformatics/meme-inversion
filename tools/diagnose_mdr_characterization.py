import collections,hashlib,itertools,json,pathlib,tarfile
base=pathlib.Path('/local/content/MEME/MEME5/inv');target=base/'sources/MDR_29_1';run=base/'qa/replay-requests/mdr-baseline-20261109';result=json.loads((run/'result.json').read_text());expected=result['comparison']['files']['attributes.src']
ref_context={};candidate_context={};changed=collections.Counter();field_changes={};history=collections.Counter();ordinary_differences=0;digest=hashlib.sha256();rows=0
with tarfile.open(target.with_suffix('.tgz'),'r|gz') as archive:
 for member in archive:
  if member.name!='MDR_29_1/src/attributes.orig':continue
  with (target/'src/attributes.src').open('rb') as fresh:
   for a,b in itertools.zip_longest(archive.extractfile(member),fresh):
    if a is None or b is None:raise RuntimeError('Different attribute row count')
    digest.update(a);rows+=1;left=a.removesuffix(b'\n').split(b'|');right=b.removesuffix(b'\n').split(b'|')
    if a!=b:
     name=left[3].decode();changed[name]+=1;counts=field_changes.setdefault(name,collections.Counter())
     for i,(x,y) in enumerate(zip(left,right)):
      if x!=y:counts[i]+=1
    if left[3]==b'CONTEXT':
     if right[3]!=b'CONTEXT':raise RuntimeError('Context/noncontext alignment changed')
     ref_context[b'|'.join(left[1:])]=left;candidate_context[b'|'.join(right[1:])]=right
    elif left[3]==b'PT_IN_VERSION':
     history['rows']+=1;history['reference_values_with_carriage_return']+=b'\r' in left[4];history['candidate_values_with_carriage_return']+=b'\r' in right[4]
     predicted=right.copy();predicted[4]=predicted[4].replace(b'\r',b'')
     history['reference_row_equals_candidate_after_removing_value_carriage_returns_only']+=left==predicted
     history['same_recorded_digest']+=left[13]==right[13]
     history['reference_digest_matches_value_with_carriage_return']+=left[13]==hashlib.md5(left[4]+b'\r').hexdigest().encode()
    else:ordinary_differences+=a!=b
if digest.hexdigest()!=expected['reference']['sha256']:raise RuntimeError('Official attribute member changed')
candidate_hash=hashlib.sha256((target/'src/attributes.src').read_bytes()).hexdigest()
if candidate_hash!=expected['candidate']['sha256']:raise RuntimeError('Fresh attributes changed')
removed=[v for k,v in ref_context.items() if k not in candidate_context];added=[v for k,v in candidate_context.items() if k not in ref_context]
by_left=collections.defaultdict(list);by_right=collections.defaultdict(list)
for row in removed:by_left[row[1]].append(row)
for row in added:by_right[row[1]].append(row)
parts=collections.Counter();sibling_only=0;child_only=0;same_sibling_multiset=0;other_fields_equal=0
for said,old in by_left.items():
 new=by_right.get(said,[])
 if len(old)!=1 or len(new)!=1:continue
 a,b=old[0],new[0];aa,bb=a[4].split(b'\t'),b[4].split(b'\t')
 if len(aa)==len(bb):
  diffs=[i for i,(x,y) in enumerate(zip(aa,bb)) if x!=y]
  for i in diffs:parts[i]+=1
  sibling_only+=diffs==[5];child_only+=diffs==[4]
  same_sibling_multiset+=len(aa)>5 and collections.Counter(aa[5].split(b'~'))==collections.Counter(bb[5].split(b'~'))
  other_fields_equal+=all(x==y for i,(x,y) in enumerate(zip(a[1:],b[1:]),1) if i not in (4,13))
input_rows=input_crlf=0
with (target/'orig/mdr_by_version.txt').open('rb') as handle:
 for raw in handle:input_rows+=1;input_crlf+=raw.endswith(b'\r\n')
report={'source':'MDR','version':'MDR_29_1','run_id':'mdr-baseline-20261109','status':'DIFFERENCES_REQUIRE_REVIEW','candidate_modified':False,'attribute_rows':rows,'aligned_changed_attribute_names':dict(changed),'aligned_changed_fields_by_attribute_name':{k:dict(v) for k,v in field_changes.items()},'history_line_endings':{'input_rows':input_rows,'input_crlf_rows':input_crlf,**dict(history)},'other_non_context_rows_changed':ordinary_differences,'context_content_differences':{'reference_only':len(removed),'candidate_only':len(added),'affected_subject_ids':sorted(int(x) for x in by_left),'changed_tab_components':dict(parts),'only_sibling_list_order_changed':sibling_only,'only_child_list_order_changed':child_only,'same_sibling_name_multiset':same_sibling_multiset,'non_value_non_digest_fields_equal_excluding_generated_aid':other_fields_equal},'scope':'Read-only diagnosis; no comparison waiver, output rewrite or production eligibility. Historical postprocessing cause is inferred, not an established operator history.'}
print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(report));print('END_COMMON_REPLAY_RESULT',flush=True)

