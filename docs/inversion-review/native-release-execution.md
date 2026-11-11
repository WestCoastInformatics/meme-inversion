# Manifest-driven native release execution

The common runner now has a native admission path alongside the [historical case catalog](common-interface.md). It derives source preparation and fixed native stages from a release manifest and a reviewed source capability, without registering a source/version replay case. The source adapters support NCIt publisher exports, US SNOMED Snapshot packages and prepared MTH bundles. MDR/RADLEX retain their existing historical runner.

Implementation status: local execution/lifecycle, physical input/output and source variation checks are implemented. NCIt tests exercise the actual Perl preparation stages; MTH tests exercise its complete thirteen-stage pipeline on tiny synthetic data. These are distinct from full dev inversions. **Additional real archived releases have not yet run through this path.** Their data completeness, source-policy compatibility and official output comparisons remain acceptance work, pending authenticated dev access. This document does not report production eligibility or full archived-release acceptance.

## Common command workflow

Use the existing pinned local Python environment and the development checkout. A real manifest uses the same [release-manifest schema](release-manifest.schema.json), with `purpose: historical-replay`, a full forty-character Git `engine_ref`, complete preserved input/state/allocation artifacts and an exact current-release reference. The [synthetic preflight examples](release-manifests.md) deliberately cannot authorize execution.

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

New MTH runs deliberately snapshot the one required prior CUI map into `sources/<current>/orig/identity/<explicit-prior>/src/cui_said_map`. Their `old` alias points to that data snapshot, preserving the converter's usual `old/src/cui_said_map` access. This is an explicit data-layout improvement: rerunning an older canonical source folder cannot change a newer candidate's captured baseline. It copies one declared data file, not an executable or full prior folder. Prefer a pinned prior archive member or stable input cache as its original locator. Existing sealed historical requests retain their original canonical-prior dependency and execution claims; inspect those consumers before replacing a folder they still reference.

Initial native admission requires local file/cache descriptors. A missing declared `inv/sources/<version>.tgz` cache can be acquired through the existing reviewed download-only S3 helper. An unresolved `s3:` pointer is rejected before a native capsule is issued. Archive SHA/size and member SHA/size remain separate. Publisher/prepared inputs are streamed selectively from tar/ZIP containers; a completed source folder is never restored into the candidate. The original official outputs remain in the existing archive and supply independently verified expected hashes, not constructor files.

Missing MTH prepared/history RRF objects can also be acquired individually at the standard `mr/umls/.../METASUBSET` paths, using the existing AWS CLI, `meme` profile and bucket. The artifact's `data.acquisition` binds `bucket` and an `objects` map keyed by file role; each value contains its exact standard-path `key` and `object_identity` (`ContentLength`, `ETag`, `LastModified`, `VersionId`). Conditional retrieval, coherent before/after object identity and the declared file hash must all agree. Existing data is never overwritten; an unresolved partial blocks another download. Capacity includes missing downloads before acquisition begins, and no additional archive convention is introduced.

Direct input or oracle URIs inside the replaceable current release folder are rejected. Use independently preserved archive members or a stable publisher cache. This avoids invalidating a frozen input URI when the existing canonical folder is preserved. New-release preparation using target-local publisher files needs a later explicit staging/rebinding contract.

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

The existing [duplicate-only retention policy](dev-retention-policy.md) applies to native runs using the verified locked source capability rather than another date allowlist. It limits expanded rollbacks and can plan compaction/recovery against the same existing official archive. Generic native `src/...` output paths are supported. Cleanup remains a separate explicit operation; this implementation work performs no real dataset deletion or archive creation.

## Remaining acceptance work

Confirm the real dependency closure for one additional archived release per source, then run them serially and investigate every difference. Candidate versions include NCIt August 2026, SNOMED March 2026 and MTH 2025AB, subject to actual archive completeness and policy compatibility. Their inserted predecessors must come from preserved evidence. Particular checks include SNOMED mapping-target VSABs, pre-insertion attribute stages and MTH's prior identity-map consumers.

Upcoming-release shadow admission without an official current output, fresh state capture, production reservations, operational QA/MRDOC and insertion remain separate gates in the [migration plan](operational-release-gates.md). The common schema vocabulary remains usable for those later capabilities without treating an unverified variation as supported.
