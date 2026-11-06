# MTH exact reproduction and consistency findings

The MTH_2026AA core replay completed on November 5, 2026, using production engine `3b125ed` and frozen prepared inputs, including the prior MTH_2025AB CUI map. **All 23 compared files are byte-identical to the official archive**, including all six core `.src` files, regenerated identity maps and preferred-term helpers. No fields, identifiers or duplicate records were ignored. Conversion took 2h 28m 43s; comparison, independent validation and final identity checks brought the total to 2h 34m 40s. The sampled peak for conversion children was 2.06 GiB. Input, code, shared-runtime and output hashes were verified after execution. [Summary](mth-2026aa-baseline-summary.json), [raw result](mth-2026aa-baseline-result.json)

The independent checker found real unresolved references in **two attribute rows and one context row**. These are also present in the official output, because the files match exactly. The verdict remains `REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS`; the findings have no waiver. [Selected records and audit](mth-2026aa-reference-findings.json)

| Issue | Observed records | Producer evidence |
|---|---|---|
| Attribute survives removal of its atom | `attributes.src` row 17,628,814 assigns a semantic type to SAID `771038403`, absent from final atoms | `make.meme4classes.s` removes two `V-CCS_2005` SRC atoms at the end. Its comment identifies an unwanted MetamorphoSys source-family inclusion. Maps and attributes were generated before this filter; `inv2.spec:38–39` emits STYs through the CUI-to-SAID map. |
| Context node has no mapped atom ID | `attributes.src` row 20,206,954 contains a LOINCPARTS context with blank subject ID; `contexts.src` row 1,118,752 has the same blank node | `mrcxt2raw3.pl:46–50` emits AUI-to-SAID lookup results without checking that they exist. Both downstream formatters accept the resulting blank ID. The context checker counts two invalid endpoint fields in this one row. |

The raw atom file retains `771038403` (SRC/VPT) and `771038404` (SRC/VAB), both `V-CCS_2005`, CUI `C1541964`. The final atom filter removes both. One semantic-type attribute still targets the first ID. This is a mismatch between the retained atom set and its dependent records.

For LOINCPARTS, the output evidence and producer code establish the missing-mapping mechanism. The exact native AUI and the intended retain/exclude treatment still require a targeted native-record trace. A follow-up SSH read could not run after the authenticated sessions ended and hostname resolution failed. No particular hardcoded CUI exclusion is asserted as the cause. This limitation does not affect the completed replay or the detailed output audit.

## Next correction candidates

First make the reviewed atom-retention policy feed identity-map creation and every dependent output. Regenerate affected maps, attributes and contexts from the retained set, then check their cross-file references. Deleting an orphan attribute alone would leave the lifecycle/state question unresolved. Preserve the original input bundle and this baseline result for comparison.

Second reject unmapped context endpoints before emitting `.raw3`, with an actionable issue identifying the source, native identifiers and intended disposition. Determine whether LOINCPARTS should map to a retained atom or be omitted under an explicit, counted policy. Do not invent an ID or silently omit the record. Once that decision is reviewed, implement it as a separate candidate and quantify every expected difference against the frozen reference.

Add checks for current identity outputs against retained atoms, in addition to the existing core-file reference checks. Keep prior/current CUI roles distinct. The existing 19 fixtures passed locally and on dev; two additional local fixtures reproduce the orphan-attribute and blank-node patterns, bringing the local total to 21. The comparator itself is unchanged from the executed full scan. [Fixture evidence](mth-2026aa-reference-findings-fixtures.json)

This completes the first MTH core reproduction, including the required prior data. Clean validation remains open work before a production candidate can be accepted. Input regeneration, historical database reconstruction, MetamorphoSys execution, legacy QA/MRDOC and insertion are separate coverage; none is needed to explain or reproduce these observed files.
