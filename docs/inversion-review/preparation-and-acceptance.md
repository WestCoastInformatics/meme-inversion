# Preparation discovery and separate acceptance review

Two common commands now support the next preparation stage and acceptance of completed native output. They use the existing release-manifest vocabulary and keep the original conversion/comparison records. Source algorithms, production paths and the historical replay interface are unchanged.

## Preparation discovery

Run locally when declared input files are on that machine:

```sh
python3 -B tools/inversion_request.py discover-release release.json \
  --output preparation-review.json
```

Use the same operation against preserved files on dev:

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  discover-release release.json --output preparation-review.json
```

Use the existing pinned Python environment with `tools/requirements-runner.txt` for local schema validation. Remote operation uses committed, hash-checked standard-library modules in a temporary directory. No installed server helper checkout is required.

The input is the existing `ncimeta-release-manifest`. A preparation draft can have `purpose: shadow`, `source_atom_ids: null` and no `configuration.replay`; an official current-release inversion is unnecessary for discovery. Keep `replacement_baseline`, `publisher_history`, input references and source options explicit. A null allocation does not invent a temporary range.

The report contains a common `issues`, `decisions`, `required_inputs`, `facts` and `input_files` structure. `decisions` contains unresolved choices; reviewed observations belong in `facts`. Outcomes are:

| Status | Meaning | CLI exit |
| --- | --- | --- |
| `DISCOVERY_COMPLETE` | Supported discovery checks completed without unresolved errors/decisions | 0 |
| `DECISIONS_REQUIRED` | Inputs can be inspected, but preparation choices or evidence remain unresolved | 3 |
| `DISCOVERY_BLOCKED` | Invalid declarations, unavailable/changed bytes, malformed input or unsupported capability | 2 |

Every outcome has `execution_eligible: false`, `production_eligible: false` and `inversion_executed: false`. Discovery completion is not executable shadow admission. The separate [`resolve-release` shadow path](qa-and-shadow-execution.md) now admits complete reviewed manifests without an official current output, with its own allocation, capacity and physical verification gates.

The reader hashes selected files/members completely, verifies full container identities and rejects linked inputs, duplicate/unsafe archive members and wrong byte counts. Unchanged archive verification is reused; ZIP members use random access. TAR members may require additional decompression passes. No archive tree is extracted and no network acquisition occurs. Failed rereads invalidate earlier verification, and the completed scan checks all selected file snapshots again. This physical consistency check does not establish coherent database/export provenance.

Official `reference-inversion` artifacts are prohibited as discovery inputs. Unavailable S3 descriptors become input requirements; acquisition remains a separate existing operation.

## Source coverage

| Source | Implemented discovery | Remaining operational evidence |
| --- | --- | --- |
| NCIt | Five publisher exports; optional source/TTY additions; unknown mappings, properties, labels and relationships; metadata and explicit predecessor/root checks | Coherent installed subsource/root/rank state, reviewed new representations, final metadata generation after allocation |
| SNOMED CT US | Snapshot roles and native headers; relationship/refset IDs and occurrences; labels, mapping/inverse/TTY choices; metadata and dependency checks | MRDOC inputs and generation/semantic validation, generic membership/prior inventory review, unresolved label normalization or mapping decisions |
| MTH | MRSAB/MRRANK inventory; saved source choices and rankings; independent inserted/publisher predecessors; prior CUI identity; declared closure and observed history | Full publisher inventory when only a prepared subset exists, unresolved dispositions/rankings/history, upstream preparation when required |

NCIt catalog membership does not prove that a subsource is already installed. Empty optional addition lists remain valid. A skipped month uses the explicitly declared inserted predecessor.

SNOMED scans retain earlier effective dates that are valid in a Snapshot package. Unknown IDs, inverse mappings and ambiguous/changed labels require decisions. An existing membership-only association review must bind the actual native identifiers/labels and original configuration/producer bytes. Supplied MRDOC files do not by themselves prove an operational documentation generator.

MTH prepared subsets support their preserved scope but cannot prove that omitted sources are absent from the full publisher release. Full inventory discovery requires a publisher-bundle `data.inventory_evidence` with `scope: full-publisher-release`, explicit `publisher_release`, `review_status: reviewed`, `review_id` and the selected `mrsab_sha256`. This records reviewed completeness evidence; it does not independently authenticate publisher completeness or implement publisher conversion. The scanner never invents REMOVE/EXCLUDE decisions. Native history observations support old AA/AB/AC/AD values, while configured current/transition identities retain their separate existing rules. Observed rows do not prove an undeclared history window complete.

MDR/RADLEX keep their existing common historical requests. Native preparation/discovery adapters remain pending.

## Acceptance of completed native output

The original result remains immutable. Use a new review identity for a separate verdict:

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  review-native release.lock.json \
  --policy mth-retained-identity-v1 \
  --diagnostic mth-diagnostic.json \
  --review-id acceptance-mth-release-001 --output acceptance-review.json
```

The MTH diagnostic must describe the same frozen lock and complete original result. The policy independently reconstructs all retained-identity changes from native data using the bounded `explain_native_mth` proof. It accepts only the characterized difference family, complete predicted maps/attributes/contexts/preferred helpers, unchanged other content and clean physical validation. It does not match a release date or hardcoded atom range. Additional differences fail the proof.

The dev entry point verifies the original parent lock and completed result, frozen source/generated/input bytes, all 169 runtime files and declared native links before/after review. The proof hashes all candidate outputs and native evidence; temporary sorting data is removed. It writes only a small separately identified QA review/status record. It performs no conversion, insertion, source output rewrite, runtime activation or S3 upload.

`PASS_WITH_VERIFIED_CORRECTIONS` is a separate accepted dev-result verdict. The original `DIFFERENCES_REQUIRE_REVIEW` stays available alongside it. This is acceptance of the preserved-input inversion scope, not production eligibility. `exact-v1` accepts only exact outputs with clean validation; it verifies the whole retained output set remains unchanged through review. Neither policy permits unresolved validation findings.

Use the existing common collection operation with the review identity to retrieve `acceptance-review.json`. The parent's `verify-native` operation retains its strict exact-result contract; this new review does not rewrite an earlier skipped verification or old capsule.

## NCIt QA decision

The [reviewed August QA decision](release-manifests/nci-2026-08e-qa-adjustment.json) records the Exposure row's SY/PT difference with exact before/after rows, hashes, native-input/reference identities and archived QA evidence. The user explicitly reviewed this exact historical adjustment on November 12; its editor remains unconfirmed. The [separate QA policy](qa-and-shadow-execution.md#reviewed-historical-ncit-qa) now validates it in a disposable classes view. Actual dev review returned `PASS_WITH_REVIEWED_QA`, with clean post-QA structural checks and complete official-output equivalence proof. All 169 runtime files were reverified. Raw conversion, the unknown-termgroup finding and the original five files remain unchanged; persistent application is unauthorized. It creates no generic DICOM/SY-to-PT rule.

## Verification and retention

The [increment evidence](preparation-and-acceptance-20261112.json) distinguishes tiny confined fixtures, public CLI/frozen-capsule checks and actual dev scans/review. Real scans can correctly return unresolved decisions; they are not successful full inversions or new-release admission proofs.

The later [QA and shadow increment](qa-shadow-execution-20261112.json) records actual historical NCIt temporary-view acceptance and the common oracle-free execution/late-reference comparison implementation. Small native shadow fixtures and declaration-only archived-input probes do not establish real predictive runs.

This work creates no new full inversion or source archive. Temporary code/sort files are removed. Compact milestone evidence records identities, verdicts and findings; routine verbose reports follow the existing 30-day development retention default. No automatic expiry service is installed.
