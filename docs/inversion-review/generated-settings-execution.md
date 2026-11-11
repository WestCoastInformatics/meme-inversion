# Generated-settings execution for SNOMED and MTH

The common interface now drives full historical native inversions with generated settings for `SNOMEDCT_US_2026_09_01` and `MTH_2026AA`. SNOMED passes byte-exact comparison against all five official core references. MTH completes native generation/comparison with clean validation and all 23 hashes matching the preceding accepted corrected candidate; a separate finalization review passes its mandatory correction audit after fixing a common-worker API error. [Independent retained-file verification](generated-settings-final-verification.json) passes for both sources, explicitly recording the MTH finalization review.

This is bounded historical execution using preserved preparation inputs and reviewed code. It does not enable arbitrary new releases or production insertion. The original nine historical cases remain unchanged; the catalog now contains eleven cases across all five sources.

## Native results and evidence

| Source | Generated files | Comparison and acceptance |
|---|---|---|
| SNOMEDCT_US | One read-only `etc/sct.cfg` | `PASS_EXACT`: all five official core files byte-identical, including pre-insertion `src/attributes.orig`; clean structural validation |
| MTH/UMLS | Four generated specifications/range files and three materialized policy-data files, all read-only | Native comparison and clean core/identity validation complete; separate review `PASS_REVIEWED_CORRECTIONS`; all 23 outputs identical to the previous accepted corrected candidate |

Original receipts: [SNOMED result](snomed-generated-configuration-result.json), [preparation](snomed-generated-configuration-preparation.json), [MTH original native result](mth-generated-configuration-native-result.json), [accepted finalization review](mth-generated-configuration-result.json), [MTH preparation](mth-generated-configuration-preparation.json), [raw comparison](mth-generated-configuration-raw-result.json), [correction audit](mth-generated-configuration-correction-audit.json).

MTH's original official files contain the previously documented reference findings. Its raw difference verdict remains preserved; the native-derived audit accounts for the reviewed corrections. Matching the previous corrected candidate does not mean matching the uncorrected official files. No columns or generated identifiers were ignored to obtain acceptance.

## MTH finalization failure and recovery

Both conversions used frozen apparatus `79df69fe5b0b45d4f3c10550c16cb62cb9e8199e`. MTH's native adapter completed generation, comparison, clean core/retained-identity validation and its input/runtime/output rechecks. The common worker then called nonexistent `mth_configuration.verify_generated`, before common post-verification and the correction audit. The original [worker status](mth-generated-configuration-parent-status.json) and [batch status](generated-settings-batch-controller.json) remain failed. The [initial independent verifier](generated-settings-initial-verification-status.json) correctly refused to run.

Fix `3a0cdca` routes that call to the existing `replay_mth_core.verify_generated`. The [new real-module regression](../../tools/check_mth_common_finalization.py) reproduces the exact frozen failure and passes 50 checks through actual package construction, staging and common finalization. Only host-runtime verification is mocked. It checks all seven generated files, source/link integrity, inclusive ID bounds, all 23 output hashes and comparison gates. The original local suites had covered recipes/staging but missed this actual common post-run call.

A separately identified [review driver](../../tools/evidence/finalize_retained_mth_generated_20261110.py), frozen at `b856830891144e57d3d37f97857e2adfceacb113`, completes the remaining verification and mandatory audit from the retained outputs. It pins the original lock, failed status, preparation/acquisition/previous-tree receipts, native result and native active receipt. It verifies the exact original module capsule and requires that the new 23-module capsule differ only by the reviewed common-worker dispatch fix. All source converters, generators, inputs and the 169-file runtime retain their original identities.

Review `common-mth-generated-finalization-20261110` passes complete input/runtime/generated-file verification, ID bounds, all output hashes and the unchanged native-derived correction audit. It rechecks the pinned parent records afterward. It does not restore/stage a source tree or repeat conversion, and does not overwrite any failed status. The original native result is copied byte-for-byte into the review record. This is **native execution followed by a separate accepted finalization review**, rather than an uninterrupted passing common-worker run.

The review has a separate scratch budget because it performs no source preservation or conversion: all 5.391 GiB of extracted references, six times the 0.721 GiB of context-derived files, a 2 GiB margin and the unchanged 12 GiB execution reserve, totaling 23.715 GiB. It also requires 24 GiB available memory. The native SNOMED 50 GiB/MTH 45 GiB launch floors were unchanged. [Review request](mth-generated-configuration-finalization-request.json), [review status](mth-generated-configuration-finalization-status.json), [fix and regression evidence](mth-common-finalization-fixtures-20261110.json).

## Same configuration, separately frozen generation

The [SNOMED request](request-examples/snomed-generated-configuration.json) and [MTH request](request-examples/mth-generated-configuration.json) retain the existing seven operator fields. Common version, baseline, input-stage and ID-bound names are unchanged. The resolver freezes generated recipes with configuration, case artifacts, source files and executable apparatus modules.

SNOMED profile `snomed-properties-v1` treats the captured configuration as a template and independent compatibility oracle. Preparation writes the generated cfg with mode `0o444`. Fourteen Snapshot inputs, two metadata files and two target inventories remain explicit historical dependencies. Settings are recomputed and checked before preparation, conversion, cleanup and final verification. The captured US package-naming restriction remains in force.

MTH profile `mth-prepared-spec-v1` generates the final range and three effective specifications, and materializes three reviewed policy-data files as seven `0o444` files. It retains the eleven-file prepared subset, eight saved metadata roles and prior inserted-version CUI map. Source descriptors remain independent historical oracles. The legacy base/SRCbuilder offset and separate publisher-previous provenance are unchanged. This profile preserves declared dispositions; it does not discover new decisions or run MetamorphoSys.

Generation inputs must agree with the actual execution dependency manifest. Changed recipes, files, modes or dependencies fail verification. The source engines are original SNOMED capture `3b125edc1d29f7c7a91673da2a8d752bb0adff44` and reviewed MTH correction `b2611abcf929981628bb2e5051afb450b8525b70`. Both conversions use the original 169-file runtime. Later review/evidence commits do not relabel the native apparatus. The [original batch controller](../../tools/evidence/run_generated_configuration_batch_20261110.py) serialized SNOMED and MTH and performed no runtime activation.

## Storage gate and retained evidence

Dev initially had 31.9 GiB free, below the unchanged native launch floors. The [retention helper](retained-source-archives.md) archived and verified three older `.before-*` test trees, then independently rechecked pinned archive receipts and unchanged expanded trees before retiring those expanded copies. Current source folders and official reference `.tgz` files were outside the selection; neither new input closure referenced the retired tree names.

The archived trees contain 295 regular files, totaling 38.710 GiB logically, retained in 5.959 GiB of compressed archives under `/local/content/MEME/MEME5/inv/qa/retained-source-archives`. File contents, modes, nanosecond modification times, empty directories and symlink targets were checked. External symlink targets remain separate dependencies. Actual free space after retirement was 59.29 GiB. No alternate canonical source layout, separate worker or S3 upload was introduced. [Actual retention evidence](dev-retention-20261110.json).

The helper passed 59 local checks, including low-space aborts, full archive verification, durability before deletion, mutation rejection, interrupted retirement and restore-aside recovery. Compression keeps a fixed 8 GiB free-space reserve. Original archive-only and retirement drivers, checksums and pinned revisions remain in the receipts.

The subsequent [dev retention policy](dev-retention-policy.md) addresses why those full folders accumulated. New common submissions allow one uncompacted rollback per source/version. Lossless duplicate-only compaction uses existing official archives instead of creating more test archives, while retaining unique files, failure records and reconstruction metadata. Historical native evidence above remains tied to its original apparatus; storage compaction is a later, separately recorded operation.

## Independent verification and fixture scope

The [independent verifier](../../tools/evidence/verify_generated_configuration_batch_20261110.py) checks original conversion capsules/locks, all 169 runtime files, source files, generated recipes and exact read-only modes, official SNOMED hashes, MTH raw/audit bindings, all 28 compared output hashes and both entire preserved predecessor trees. Its reviewed mode explicitly requires the original MTH failure and initial verifier refusal, the accepted separate review, unchanged parent records and the exact worker-only API fix. It also rehashes all three retained archives after retirement. The completed scan verifies all 28 outputs, one/seven generated read-only files, all 169 original runtime files per case and the complete 59-entry SNOMED/133-entry MTH preserved trees. It ran offline in 403.29 seconds. [Original final report](generated-settings-final-verification.json), [execution metrics](generated-settings-verification-metrics.json), [byte-preserved receipt identities and audit bindings](generated-settings-receipt-identities.json).

The [original local fixture record](generated-execution-fixtures-20261110.json) contains 411 integration checks, 59 retention checks and four detached-verifier scenarios. [Operational follow-up fixtures](operational-preparation-fixtures-20261110.json) add 71 NCIt backend-contract checks and 29 MTH preparation checks. The [finalization fix record](mth-common-finalization-fixtures-20261110.json) adds the real common-path 50 checks and records the subsequent 95 request/30 generated-execution regression checks. These are distinct scopes; local/synthetic checks are separate from full native evidence.

## Parallel operational preparation follow-up

The [NCIt v2 backend-state preflight](nci-backend-preflight-v2.md) verifies raw field bindings, source-SAID identity, explicit backend-version aliases and separate default/project rankings. Every result retains six capture blockers; no deployed exporter or coherent capture is inferred. Timestamp checks work without an optional format package. [Deployment inspection candidates](nci-deployment-inspection-candidates.md) identify the next primary-code-backed evidence to obtain.

The separate [MTH preparation candidate](mth-preparation-corrections.md) rejects invalid prior dispositions, preserves failed proposals and fixes the installed-source disposition field. Its 29 confined checks exercise actual revised scripts, valid-byte compatibility and permission preservation. These changes are committed for review, with no deployment or complete upstream MetamorphoSys acceptance. The native conversion retained `b2611ab`, whose prepared-input path does not invoke those scripts.

Operational releases still need reviewed source decisions/state, real allocation, legacy QA and insertion gates. NCIt's historical mapping/ranking findings and source-specific global-TTY flag findings remain explicit. See the [next operational gates](operational-release-gates.md).

## Connection and development handling

The Mac's Cisco profile already enabled automatic reconnection after resume. Temporary `caffeinate -i` guards prevented idle sleep and were renewed for the long work; managed VPN policy and gateway timeouts were unchanged. SSH uses 30-second keepalives. Conversion, review and verification controllers run detached on dev, so VPN loss does not stop them. Reconnect and collect the original run/review identity rather than resubmitting conversion.

The three clean terminology development worktrees/branches were removed only after their commits were merged and verified published at `81a6d01`. Their histories remain in `test/inversion-replay-toolbox`; `main` is unchanged.
