# Manifest-driven native release execution

The common runner now has a native admission path alongside the [historical case catalog](common-interface.md). It derives source preparation and fixed native stages from a release manifest and a reviewed source capability, without registering a source/version replay case. The source adapters support NCIt publisher exports, US SNOMED Snapshot packages and prepared MTH bundles. MDR/RADLEX retain their existing historical runner.

Implementation status: local execution/lifecycle, physical input/output and source variation checks are implemented. NCIt tests exercise the actual Perl preparation stages; MTH tests exercise its complete thirteen-stage pipeline on tiny synthetic data. For additional real archived releases, NCIt August retains raw `DIFFERENCES_REQUIRE_REVIEW` alongside a separate passing temporary-view reviewed-QA acceptance; SNOMED March completed with `PASS_EXACT` and passed fresh-process retained verification; MTH 2024AA completed all thirteen stages and passed physical validation, with fourteen of twenty-three compared files byte-exact and nine accepted through a separate verified-correction review while their raw differences remain preserved. [Core shadow execution and later reference comparison](qa-and-shadow-execution.md) are now implemented; real upcoming-release predictive runs remain to be demonstrated. This document does not report production eligibility.

The initial [verification record](native-release-execution-fixtures-20261111.json) records 862 passing local checks across twelve suites. Separate committed-code probes freeze and re-import all three native capsules using the standard library only, reject the honest synthetic examples and verify all eleven historical requests. The prior accepted SNOMED/MTH generated recipes, source files and runtime payloads remain identical. The native serialization probes use synthetic declarations solely as test scaffolding; they do not establish real input provenance or native release acceptance. The genuine release reviews below separately record the newly captured archive evidence and source variations.

## Genuine archived release manifests

| Source | Test release | Explicit inserted predecessor | Actual dev result | Manifest and input review |
| --- | --- | --- | --- | --- |
| NCIt | `NCI_2026_08E` | `NCI_2026_07D` | Raw differences preserved; separate temporary-view reviewed-QA acceptance passed | [Manifest](release-manifests/nci-2026-08e.json), [review](release-manifests/nci-2026-08e-review.json) |
| SNOMED CT US | `SNOMEDCT_US_2026_03_01` | `SNOMEDCT_US_2025_09_01` | All five outputs byte-exact; independent verification passed | [Manifest](release-manifests/snomed-2026-03-01.json), [review](release-manifests/snomed-2026-03-01-review.json), [association decision](release-manifests/snomed-2026-03-01-association-review.json) |
| MTH | `MTH_2024AA` | `MTH_2023AB` | All thirteen stages complete; clean physical validation; fourteen of twenty-three files byte-exact; separate corrected acceptance passed | [Manifest](release-manifests/mth-2024aa.json), [review](release-manifests/mth-2024aa-review.json), [result](mth-2024aa-native-results-20261112.json) |

These manifests contain real preserved input and reference identities. They use the same common commands below and do not add release-specific execution cases. Their review records explicitly distinguish input curation, synthetic checks, native execution and official comparison.

The August diagnostic establishes two byte-exact outputs, context rows identical with different ordering, and attribute row multisets identical after excluding only generated attribute IDs. Exactly one atom field differs: DICOM/SY in the native input and generated output versus DICOM/PT in the official output. Archived QA flags that same atom as an undefined SY termgroup, supporting a correction after the captured QA state; the actor is unconfirmed. Its manifest preserves the publisher input and strict output checks. The diagnostic grants no comparison or validation waiver. This is a reason to preserve generated output, approved output and explicit QA decisions as distinct workflow records in the future.

March's saved metadata uses terminal delimiters; the adapter preserves that declared wire format. One association has a reviewed membership-only representation already implemented by the captured native converter. Its policy binds the actual native files, archived configuration and producer, and independently checks exact membership attributes and absence of relationship edges. This does not enable an arbitrary missing mapping.

MTH's complete staff plan contains background source choices handled outside its REST subset. The prepared selection is checked against the original staff files, saved VSAB updates, installed inventory and MRSAB. An already-installed SNOMED UPDATE remains a recorded background choice; selected same-version updates and arbitrary omissions remain errors.

The actual 2024AA conversion finished on November 12 at 02:27 UTC (November 11 at 18:27 Pacific). Final atoms, relationships, merge facts and bequeathal relationships are byte-exact. Full identity-map comparisons find only two obsolete CCS AUI entries removed and one LOINCPARTS entry restored; each CUI map removes the corresponding CCS binding and adds the LOINCPARTS binding. Original unfiltered atom allocation is byte-exact; retained raw atoms and preferred-order helpers differ only by the corresponding CCS deletions. The complete native-derived explanation now accounts for all nine differing files. It predicts the full old/new maps from unchanged allocations, removes one CCS semantic-type attribute and adds one LOINCPARTS semantic-type attribute from MRSTY, and verifies all 18,233,753 native attribute positions and every generated ID. All other native attribute content is preserved in order. One blank native-bound context and its context attribute receive the restored identity; complete sorting/re-ID predictions reproduce both candidate file hashes, preserving every other field and duplicate occurrence. All twenty-three candidate hashes, three full native input hashes and 169 runtime files were reverified, and temporary sort data was removed. The conditional exact-result verifier correctly skipped this strict difference result. The separate diagnostic grants no acceptance waiver.

## Common command workflow

Use the existing pinned local Python environment and the development checkout. A real manifest uses the same [release-manifest schema](release-manifest.schema.json), a full forty-character Git `engine_ref` and complete input/state/allocation artifacts. `purpose: historical-replay` requires an exact current-release reference. [`purpose: shadow`](qa-and-shadow-execution.md) instead prohibits that dependency and requires a reviewed output/scratch planning budget; it cannot claim an official match before separate later comparison. The [synthetic preflight examples](release-manifests.md) deliberately cannot authorize execution.

```sh
python3 -B tools/inversion_request.py resolve-release release.json \
  --run-id source-release-test-001 --output release.lock.json

python3 -B tools/inversion_request.py show release.lock.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  inspect-current release.lock.json --output previous-source.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  activate-runtime release.lock.json --output runtime-activation.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  submit release.lock.json --previous-receipt previous-source.json \
  --output launch.json
```

Use new filenames and a new run ID. `resolve-release` freezes `ncimeta-native-release-lock`, a different artifact from the non-executable preflight review lock. It requires committed consumed code, schemas and profile bytes. It records the complete source plan, generated files, Git code, source capability, runtime and artifact dependencies. The worker reconstructs the source-owned deterministic plan before accepting a capsule; an altered native argument array cannot be approved by merely resealing a plan hash.

`resolve-release` performs declaration preflight internally. The separate `preflight-release` command remains useful for inspecting detailed findings; its preview reports/review locks do not grant execution and retain exit code 3. `show` displays either historical or native configuration without dumping executable payloads. Common status/collection obtains the actual source/version from run metadata or its locked request rather than a historical date table.

The [native capability registry](native-execution-profiles.json) pins source package inventories, the complete 169-file runtime, the existing S3 helper identity and source capacity floors. Package identities are independent of release dates. The source declaration registry continues to describe declaration preflight; the separate native capability performs execution admission. Fresh NCIt backend captures still need their existing assurance gates. The NCIt preserved-preparation profile consumes exact archived configuration and metadata as data without claiming a new exporter or coherent live capture was authenticated.

## Inputs, prior releases and official references

Candidate files use `sources/<version>/...`, and MTH prepared data retains `mr/umls/<release>/subsetN/METASUBSET`. Reused data must match frozen bytes and cannot traverse linked ancestors. Existing files and permissions are preserved; differing data is never overwritten. Source executables come only from the canonical Git package.

New MTH runs snapshot the one required prior CUI map into `sources/<current>/orig/identity/<explicit-prior>/src/cui_said_map`. Their `old` alias points to that data snapshot, preserving the converter's usual `old/src/cui_said_map` access. The original locator must also be independent of replaceable source folders, since retained verification and future fresh replays reopen declared inputs.

The explicit immutable cache location is `inv/qa/prior-identity-cache/<prior-version>/<full-map-SHA256>/cui_said_map`, alongside a sealed receipt. `cache_mth_prior_identity.py` publishes one independent read-only data copy, verifies the original capture and map facts, and reuses a valid cache without reopening the old canonical folder. Actual 2023AB publication preserved all 40,587,724 bytes and 2,136,196 CUI rows. This small input-cache addition protects release lifecycle independence; source folders, prepared UMLS locations and native `old/src` access remain unchanged. The original canonical stub and earlier records are preserved. Existing sealed historical requests retain their original dependency and execution claims; inspect those consumers before replacing a folder they still reference.

Initial native admission requires local file/cache descriptors. A missing declared `inv/sources/<version>.tgz` cache can be acquired through the existing reviewed download-only S3 helper. An unresolved `s3:` pointer is rejected before a native capsule is issued. Archive SHA/size and member SHA/size remain separate. Publisher/prepared inputs are streamed selectively from tar/ZIP containers; a completed source folder is never restored into the candidate. The original official outputs remain in the existing archive and supply independently verified expected hashes, not constructor files.

Missing MTH prepared/history RRF objects can also be acquired individually at the standard `mr/umls/.../METASUBSET` paths, using the existing AWS CLI, `meme` profile and bucket. The artifact's `data.acquisition` binds `bucket` and an `objects` map keyed by file role; each value contains its exact standard-path `key` and `object_identity` (`ContentLength`, `ETag`, `LastModified`, `VersionId`). Conditional retrieval, coherent before/after object identity and the declared file hash must all agree. Existing data is never overwritten; an unresolved partial blocks another download. Capacity includes missing downloads before acquisition begins, and no additional archive convention is introduced.

For a first capture whose SHA values are not yet known, `capture_mth_prepared.py` conditionally retrieves exactly eleven selected objects, computes their full hashes and record facts, and publishes one sealed standard-path cache. Its separate 12 GiB acquisition reserve does not satisfy or lower the 45 GiB native execution floor. `capture_mth_prior.py` streams a conditional prior source archive, checks the complete compressed hash and gzip integrity, and retains only `src/cui_said_map` plus its receipt. The actual 2023AB capture completed without retaining another full prior archive. Neither helper regenerates historical database state or executes archived scripts.

New native admissions reject input or oracle URIs inside any replaceable source tree, including prior and retained folders. Encoded parent aliases are normalized before this check. Top-level frozen `sources/<version>.tgz` archives, immutable input caches and declared prepared UMLS caches remain supported. This prevents a later replay or preservation operation from invalidating another release's declared inputs. Existing frozen capsules preserve their original code and rules. New-release preparation using target-local publisher files needs a later explicit staging/rebinding contract.

`replacement_baseline` remains the last inserted release, even when a calendar month or publisher release was skipped. MTH publisher-previous history is separate. An archived prepared bundle can close the necessary history without rebuilding old database queries or MetamorphoSys. Optional original MTH decision files are preserved as data and physically reconciled with the typed plan; current archive-curation hashes do not claim the historical producer recorded this new JSON format.

The replay reference is the current release's `inversion-src` output. Its file roles are the complete candidate-relative output paths (`src/classes_atoms.src`, etc.). Select `attributes.orig` as the archive member when that is the proved pre-insertion output; its logical role remains `src/attributes.src`. A prior comparison baseline or insertion-augmented attributes cannot substitute for this oracle.

## Execution and retained-file verification

Submission remains limited to `tomcata` on `ncias-d3777-c`. The same global runtime lock serializes preparation, conversion and comparison. The worker rechecks capacity after acquisition and before preserving the current folder; streamed input copies and native stages retain the fixed disk reserve. Native stages use a network namespace with the current account, bounded resources and fixed arguments from the source adapter. No insertion, live allocation, database export or upload is performed.

Inputs and references pass byte verification before preservation. Physical publisher/prepared/state validation runs before candidate publication. An existing folder needs a matching inspection receipt; changed state blocks replacement. If preparation fails before publication, the original tree can be restored. Published partial candidates, failed states and logs remain investigation evidence. No automatic dataset archive is created.

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  status --source NCI --run-id source-release-test-001 --output status.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  collect --source NCI --run-id source-release-test-001 --output result.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  verify-native release.lock.json --output retained-verification.json
```

The initial acceptance profile requires exact complete output hashes and independent source structure/identity checks. Differences remain `DIFFERENCES_REQUIRE_REVIEW`; the historical 2026AA MTH correction waiver is not generalized to other releases. A separate read-only verification process rehashes input/reference bytes, source/generated files, runtime and outputs and compares them with the original completed result. It does not repeat conversion or modify original evidence.

The [retention policy](dev-retention-policy.md) limits expanded rollbacks and supports both archive-backed lossless compaction and deliberate disposal of obsolete test bulk. Generic native `src/...` output paths are supported. Cleanup is a separate explicit operation. The approved MTH retirement below discarded only obsolete test data, with no new archive or S3 upload; it did not change native conversion or comparison rules.

## Remaining acceptance work

The [separate common acceptance review](preparation-and-acceptance.md) now accepts MTH 2024AA under `mth-retained-identity-v1` as `PASS_WITH_VERIFIED_CORRECTIONS`, preserving the original raw differences. Its fresh dev verification checked all 169 runtime files and 12 planned links plus the complete native-derived proof. Fresh conversion, strict official comparison and the complete native-derived explanation are finished; the raw result remains `DIFFERENCES_REQUIRE_REVIEW`, with clean physical validation. The read-only tools `diagnose_native_mth.py` and `explain_native_mth.py` explain the existing result without executing another inversion or changing source data. Their 39 and 15 confined checks remain distinct from the actual archived-release evidence. That release was selected because its required prepared objects and predecessor map are available; the inspected standard 2025 prepared-input prefix was empty. Its 45 GiB execution gate remains unchanged. The [authorized retirement](mth-bulk-retirement-20261111.json) removed 43 obsolete generated files totaling 28.199 GiB from three older MTH test copies. The independent postcheck found 46.9 GiB free and confirmed current accepted outputs, prior maps, archive metadata and runtime unchanged. No disk expansion was needed for this run. The frozen `native-mth-2024aa-cache-20261111` request launched after that verification and completed all thirteen stages.

The earlier [capacity review](native-storage-review-20261111.json) found at most 18.4 GiB of sharable identical prefixes, insufficient by itself. Its read-only block-sharing plan was never applied. Subsequent explicit approval to discard obsolete generated files resolved the capacity gate through retirement instead. That distinction matters: lossless compaction and filesystem sharing preserve bytes, while a finished investigation can authorize disposal of unneeded scratch files. The default now keeps compact milestone identities/verdicts and gives routine verbose evidence a 30-day expiry rather than retaining every run detail indefinitely.

NCIt retains its original strict review result. The user-reviewed exact historical adjustment now passes a separate temporary-view QA acceptance and full comparison contract on dev, with all raw files unchanged and scratch removed. This authorizes no persistent rewrite or generic mapping. SNOMED March requires no further conversion or comparison for this increment: all five outputs match the pre-insertion reference bytes, all physical output checks pass, and a fresh process reverified 26 input/reference descriptors, all 169 runtime files and the retained outputs.

Core shadow admission without an official current output is implemented through the same manifest/worker. Its local verification and separate late-reference comparison are described in [QA and shadow execution](qa-and-shadow-execution.md). Real predictive trials, late corrected-difference review/retention integration, fresh state capture, production reservations, operational QA/MRDOC and insertion remain gates in the [migration plan](operational-release-gates.md).

The [preparation/discovery command](preparation-and-acceptance.md) now reports source decisions before allocation and without an official output. Real preserved-input scans for all three sources completed with explicit remaining decisions. These scans do not grant executable shadow admission.
