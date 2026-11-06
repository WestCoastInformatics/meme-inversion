# MTH retained identity corrections

Status, November 6, 2026: full corrected replay complete with clean independent core/identity validation. Native-derived difference audit passes with every changed record and generated ID accounted for. The first audit exposed an omitted framework type in its final guard; that attempt is retained alongside the source-backed correction and passing retry. No production deployment, insertion or reference waiver.

## Confirmed causes

The unchanged production replay matched all 23 official files. Its three invalid rows have two causes; exact reproduction and valid output are separate gates.

1. Final atom formatting removed the two unwanted `SRC` / `V-CCS_2005` atoms after maps and dependent records had been created. One semantic-type attribute still targeted SAID `771038403`. The existing retention policy belongs before identity-state derivation. Allocation still visits the original native rows, so retained atom IDs keep their original values and the removed atoms leave gaps.
2. `invert2.s` removed CUI `C1976636` from the current AUI map even though its LOINCPARTS atom was retained. The original pre-exclusion mapping was `A32818398|C1976636|N|771405764`. Native MRCONSO row 2,575,834 contains that HC atom. Native MRCXT rows 7,740,634 and 14,844,501 contain the root-child and LOINCPARTS self records. The map-only exclusion leaves three raw context records with an unresolved subject and/or related identity; the final output has one invalid context row and its invalid CONTEXT attribute. The archived QA/readme/checklist material supplied no intentional exclusion policy.

## Separate source commits

Branch `fix/mth-consistent-identity-state` starts directly from production `3b125edc1d29f7c7a91673da2a8d752bb0adff44`.

- `2dd33f2`: both effective `inv1.spec` files allocate the original atom sequence into a non-insertion intermediate, then select retained atoms before maps are derived. Final formatting no longer makes an additional atom-selection decision. Twelve fixtures execute the actual legacy/candidate producers and check exclusions, retained near matches and stable SAIDs.
- `b2611abcf929981628bb2e5051afb450b8525b70`: removes the map-only C1976636 exclusion. `mrcxt2raw3.pl` requires positive numeric mappings for both endpoints, reports native source/code/context/AUI identifiers on failure, checks the sorter exit and publishes a complete file by rename. Failed generation preserves any prior canonical raw file. Fifteen fixtures cover native retained identities, byte-identical valid serialization, missing/invalid mappings and sorter failure.

All 27 checks pass on macOS and dev Linux. Dev `/tmp` is mounted `noexec`; executable test fixtures run in a temporary directory on the existing inversion source filesystem and are removed afterwards. No data directory was relocated. [Source fixture receipt](mth-2026aa-source-correction-fixtures.json)

## Full replay and acceptance

Run `candidate-consistent-state-20261106` uses the same archives, eight saved metadata inputs, eleven prepared subset files, prior MTH_2025AB CUI map and all 169 unchanged shared runtime files. Its apparatus is pinned separately to `637af4ea5b83584bd7eb4863c3399742808ae5e5`. The exact baseline was verified and retained at `MTH_2026AA.before-consistency-20261106`; generated outputs were not seeded into the new candidate. All 57 source code/link entries come from the candidate Git revision. Five producer paths differ from production. [Frozen case](mth-2026aa-consistency-case.json), [launch](mth-2026aa-consistency-launch.json)

Acceptance requires the complete comparison, independent file/reference checks, retained-atom identity-state checks, and an explicit explanation of every changed record and generated identifier. A list of potentially affected outputs only defers intermediate exact-hash checkpoints; it does not waive the final comparison. The final atom IDs/content, unrelated history outputs and source metadata should remain stable. Native LOINCPARTS dependencies and records derived from the removed CCS identities must be assessed from the full output, without assuming the correction affects only the original three bad rows.

The original result remains `REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS`. A corrected candidate cannot inherit its exact-match claim or become production eligible merely because independent checks pass.


The corrected replay completed at 21:27 UTC on November 6. All six core files and five identity maps pass independent validation. Fourteen of 23 compared files are exact, including final atoms, relationships, mergefacts and bequeathal relationships. Nine differences are retained in the raw `DIFFERENCES_REQUIRE_REVIEW` result. The final attributes file has the same row count and 27 additional bytes; contexts have the same row count and 18 additional bytes. The AUI map removes the two known CCS bindings and restores the native LOINCPARTS binding. [Raw corrected result](mth-2026aa-consistency-result.json), [summary](mth-2026aa-consistency-summary.json), [audit method](mth-correction-audit.md).


The independent native-derived correction audit subsequently passed. It predicts the complete retained maps and helpers, one removed CCS semantic-type attribute, one restored LOINCPARTS semantic-type attribute, one corrected context row and its CONTEXT attribute. Every generated-ID shift is explained by those changes and context reordering. All 6,404,200 relationships remain exact. [Passing audit](mth-2026aa-correction-audit-result.json).
