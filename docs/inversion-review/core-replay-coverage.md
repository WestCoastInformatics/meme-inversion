# Core replay coverage and the next migration gate

Updated November 9, 2026 (Pacific time). The common historical replay framework has accepted cases for all five sources. Six full common executions are recorded below. All work used the separate dev server and storage at the mirrored operational paths; production is unchanged.

The [November 10 branch consolidation](branch-consolidation-20261110.md) retains the exact tested engines and original production snapshots with annotated tags. The common working branch now includes the reviewed MTH/MDR corrections; all historical case and apparatus commit identities remain unchanged.

| Historical case | Common execution result | Additional evidence |
|---|---|---|
| NCI_2026_10D, reviewed PT/order fixes | [PASS_EQUIVALENT](common-nci-2026-10d-result.json) against the official pre-insertion reference | All three native TREF files match; all five output hashes match the earlier stable candidate; explicit August replacement baseline retained |
| SNOMEDCT_US_2026_09_01, unchanged engine | [PASS_EXACT](common-snomed-2026-09-01-result.json), all five core files | Complete original cleanup, independent full-file validation and actual report collection |
| MTH_2026AA, retained-identity corrections | [PASS_REVIEWED_CORRECTIONS](common-mth-2026aa-clean-result.json), one uninterrupted common lifecycle | All 23 output hashes match the earlier corrected replay; independent native-derived difference audit and clean core/identity checks |
| MDR_29_1, history/context corrections | [PASS_REVIEWED_CORRECTIONS](common-mdr-29-1-result.json) | Complete attribute-file and generated-ID prediction; all five hashes match the two previously verified runs with different Perl hash seeds |
| RADLEX_4_3, unchanged source with original runtime | [PASS_EQUIVALENT](common-radlex-4-3-baseline-result.json) | Fresh generation and all three original cleanup stages; independent checks |
| RADLEX_4_3, unchanged source with stable-order runtime | [PASS_EQUIVALENT](common-radlex-4-3-stable-result.json) | Same prepared inputs and cleanup stages; full changed-library regression |

The [final read-only verification](common-matrix-final-verification-20261109.json) rehashed all compared outputs in the six retained trees, their frozen inputs, code, execution modules and input archives. The [exact executed verifier](../../tools/evidence/verify_common_matrix_20261109.sh) is retained with its recorded SHA256; it requires dev/tomcata and the same retained case paths. The original shared runtime's 169 file hashes were independently verified after restoration. Its runtime metadata has a new activation receipt; this is not a claim that the previous receipt's bytes were restored.

The [common interface](common-interface.md) provides one seven-field request, typed source options, immutable case locks, explicit data/identity dependencies, fresh preparation from Git code, prior dev-tree preservation, serialized execution, comparison, mandatory correction audits where required, status and collection. The captured operational code remains the authority; reviewed producer fixes have separate engine revisions. Earlier prototype automation does not define these contracts.

Matching an official reference and proving a producer correction are different acceptance paths. The original MTH reference findings, original MDR differences and earlier failed jobs remain recorded. Corrected MTH/MDR runs preserve their raw difference results and require independent native-input-derived checks. Neither an intentional correction nor a client reconnection relabels an earlier failed job. NCIt's actual [VPN reconnection](common-client-reconnection-20261109.json) reused its original detached worker and collected the completed result without resubmitting it.

The [shared-runtime matrix](shared-runtime-regression-matrix-20261109.json) closes the bounded context-order regression: NCIt, MDR and RADLEX have actual full runs on the changed runtime. The selected SNOMED writer uses its own context output; MTH's selected pipeline has no dependency on the changed method. Their evidence combines inspected versioned code paths with original-runtime common integrations. No alternate-runtime full execution is claimed for those two sources. The six executions retain their actual, differing apparatus revisions.

A complete preserved input bundle is sufficient for a historical core replay. Recreating its historical database, metadata exports or MetamorphoSys runtime is optional further coverage. Prior-release identity state, replacement baseline, comparison oracle and the previous dev tree are distinct roles. Reference members are chosen per output; SNOMED, MDR and RADLEX use pre-insertion `attributes.orig`, including their original semantic type. Generated official outputs are not seeded into fresh candidates.

The next migration gate is operational release creation: generate legacy settings from the common configuration, select executable code from pinned Git revisions, restore only declared data/identity dependencies through the existing S3 tools, and remove manual executable copy-forward. Keep skipped NCIt months explicit. Preserve source-specific representation policy while migrating transformations incrementally.

This completes the five-source historical core framework boundary. General new-release configuration generation, upstream metadata/ICD/CSV/subset acquisition, live ID reservation, legacy database QA/MRDOC, insertion, production eligibility and deployment remain separate work. RADLEX's historical emitted-ID bounds are verified; its production reservation end is not inferred. The broader [assessment](assessment.md) and [test architecture](test-architecture.md) retain those later gates.

## NCIt generator pilot completed November 10

A subsequent [generated-configuration replay](nci-configuration-generation.md) replaces source-folder code/configuration copying with four canonical Git scripts and a read-only configuration rendered from the common model. All 290 effective native settings agree with the verified configuration; all three TREF files and all five core output hashes are unchanged. The [separate final verification](nci-configuration-final-verification.json) also confirms the entire previous dev tree and restored original runtime. The earlier six-case matrix remains dated evidence; its previous NCIt candidate is now retained under `NCI_2026_10D.before-common-nci-generated-20261109`. Other sources' generators and general operational release creation remain later gates.

## NCIt optional source/termgroup plans completed November 10

The [source-plan extension](nci-source-plan.md) replaces the hardcoded BLOODPAC emitter and archived-metadata seeding with reviewed data, generated metadata and an explicit ordered root list. The [fresh full run](nci-source-plan-summary.json), using source engine `b6c60b4` and apparatus `0df06fa`, passes with all five core files byte-exact to the preceding accepted generator candidate, all three TREF files exact and both generated metadata files equal to their independent archive hashes. Only five publisher files seed the new candidate.

[Independent final verification](nci-source-plan-final-verification.json) rehashes all compared files, frozen code, native/archive inputs, generated files, the entire 47-entry preserved prior tree and all 169 restored original runtime hashes. The prior candidate now lives at `NCI_2026_10D.before-common-nci-source-plan-v2-20261110`. The existing matrix and earlier receipts retain their dated identities. Runtime metadata has a new restoration receipt.

The current validation/catalog-promotion code passes 205 local checks and recomputes the exact executed recipe. Actual following-release Perl fixtures confirm that promoted long-source and term-type bindings work with empty addition lists. The post-replay validation/promotion revision is recorded separately; the native receipt is not relabeled.

`CTCAE 6.0` has no captured mapping, and the preserved BLOODPAC/SY low-termgroup target is absent from its metadata bundle. Those declared, input-bound historical findings are retained for compatibility, not waived for operational use. Fresh baseline/root inventory, arbitrary release registration, source removals, production allocation, legacy QA and insertion remain later gates.
