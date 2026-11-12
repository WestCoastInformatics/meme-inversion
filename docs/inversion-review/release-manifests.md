# Release manifests and common preflight

This increment implements the first deliverable in the [generalization plan](operational-release-gates.md): one versioned release manifest, reviewed source profiles, three source-specific preflights, examples and a common command. It does not select a historical replay-catalog case. The same preflight handles two distinct synthetic release transitions for each source using manifest data alone.

The subsequent [native execution implementation](native-release-execution.md) adds `resolve-release` and common worker dispatch for preserved historical manifests. Local fixture validation is implemented. Additional real dev evidence now includes a byte-exact, independently verified SNOMED March conversion, a completed NCIt August conversion retaining strict review after diagnosis, and a completed MTH 2024AA conversion with clean physical validation and fourteen of twenty-three files byte-exact, while nine retain strict review. Declaration reports and review locks still explicitly report execution and production eligibility as false. Existing historical requests and their accepted native evidence remain unchanged.

## One editable configuration

The [manifest schema](release-manifest.schema.json) wraps the common configuration vocabulary with a source profile and named artifacts. Configuration schema version 2 adds explicit pending allocation and test/production range kinds while retaining names such as `replacement_baseline`, `publisher_history`, `inputs.identity_state` and `source_atom_ids`. Existing configuration schema version 1 is not modified.

An operator's configuration refers to readable artifact names such as `publisher`, `saved-root` or `allocation`. Preflight fingerprints the complete typed artifacts, including their provenance, files and data. Operators do not need to calculate canonical JSON hashes to name them. Published input bytes still need independently declared SHA-256/size identities from their producer or acquisition process.

| Role | Meaning |
|---|---|
| `version` | Current source release to prepare |
| `replacement_baseline` | Explicit last inserted release; never inferred from the prior month |
| `comparison_baseline` | Independently selected baseline for transition/change analysis |
| `publisher_history` | Additional declared publisher history dependencies |
| `inputs.source_data` / `source_data_stage` | Publisher inputs or a preserved prepared bundle |
| `inputs.reference_ncimeta` | The selected source's saved metadata/state bundle |
| `inputs.identity_state` | Required saved roots or persistent identity maps |
| `inputs.source_plan` | Release-specific reviewed source decisions |
| `replay.reference_ref` | Optional official inversion oracle for the current release, separate from prior baselines |
| `source_atom_ids` | Inclusive bounds plus provenance; null reports a missing-allocation blocker |

An official replay reference must match the current release and candidate output stage, and its producer artifact must bind `data.reference_stage` explicitly. Insertion-augmented attributes cannot silently substitute for inversion-stage output. Official output artifacts cannot be selected as publisher/prepared candidate input bundles.

Artifacts distinguish publisher/prepared inputs, metadata state, identity, policy, source plans, allocation, publisher history, official references and environment/validation profiles. The common [profile registry](source-profiles.json) and its [schema](source-profiles.schema.json) identify reviewed capabilities rather than enumerating release dates. Canonical engine package bytes must agree with a reviewed engine; unrelated Git commits do not require new release-specific engine entries when the package contents are identical.

## Run the common command

Use the existing pinned Python environment from [the common runner instructions](common-interface.md). These checked-in examples are explicitly synthetic and always remain blocked as operational evidence:

```sh
python3 -B tools/inversion_request.py preflight-release \
  docs/inversion-review/release-manifest-examples/nci.json \
  --verify-files --output /tmp/nci-release-preflight.json

python3 -B tools/inversion_request.py preflight-release \
  docs/inversion-review/release-manifest-examples/snomed.json \
  --verify-files --output /tmp/snomed-release-preflight.json

python3 -B tools/inversion_request.py preflight-release \
  docs/inversion-review/release-manifest-examples/mth.json \
  --verify-files --output /tmp/mth-release-preflight.json
```

The examples verify 5 NCIt, 18 SNOMED and 20 MTH tiny fixture files. Reports retain schema validity, declaration validity, resolved artifact/code identities, per-file verification, source findings, planned compatibility paths and execution blockers separately. `planned_outputs` names expected files; this increment does not render or stage those files.

The [local verification record](release-manifest-fixtures-20261111.json) records 574 passing checks: 370 new contract/source checks and 204 existing regression checks. A separate public CLI smoke test freezes all three review locks using actual committed code, verifies all 43 example files and confirms worker rejection. All eleven historical requests also resolve and pass lock verification from committed code; the prior accepted SNOMED/MTH execution recipes, source packages and runtime remain identical. Six synthetic transitions exercise manifest variation; no new full native inversion ran during this increment.

Exit 3 means a retained readiness-blocked report; exit 2 means invalid input/contract or an output collision. File declarations without `--verify-files` remain explicitly unverified. New destinations are required, and existing reports are never overwritten.

Optional `--lock-output /tmp/release-preflight.lock.json` freezes a review lock after all consumed code/schemas/profiles are committed. It binds the original manifest hash, complete artifact fingerprints, engine/profile resolution, file verification and code provenance. It rechecks current provenance and input identity/change-time snapshots before freezing. Dirty bytes are not labeled as HEAD. This is a distinct **non-executable preflight lock**, not an accepted dev replay lock or general worker admission. Keep the source manifest with its review lock; the lock identifies it by hash rather than duplicating the full manifest. The existing worker rejects this artifact type.

## File verification and preserved inputs

Common descriptors use `role`, `uri`, `sha256` and `bytes`. An archive member additionally declares `archive_member`, `archive_sha256`, `archive_bytes` and explicit `archive_format` (`tar.gz` or `zip`). SHA-256/size for the member and its containing archive have distinct fields.

`file:///...` reads local regular files. `s3://...` records unresolved remote inputs and performs no download; use the existing acquisition workflow to make the exact bytes available before verification. `repo:tools/fixtures/release-manifests/...` is restricted to explicitly synthetic examples. A known fixture location cannot be relabeled as real evidence merely by changing URI spelling.

The verifier groups members from the same archive, hashes the container once, streams selected payloads and creates no extraction tree or archive copy. Traversal, linked input paths, selected archive links, duplicate/noncanonical members, changed sizes/checksums, unsupported ZIP data and stale file snapshots block verification. Byte/ID counts require exact integer values.

Verified bytes do not authenticate producer claims or prove that a declared header/discovery/metadata summary matches every native record. Source preflight states its declaration scope explicitly. Full semantic discovery and conversion validation remain later gates. Preserved prepared inputs remain valid dependencies; their original database queries or producer runtime need not be reconstructed merely to consume them.

## Source coverage and remaining work

| Profile | Implemented source checks | Remaining execution work |
|---|---|---|
| `nci-publisher-inputs-v1` | Five publisher roles, explicit skipped-month baseline, optional additions, representation catalog, saved hierarchy root and declared state/ranking checks; actual August native conversion complete with diagnosed differences | August retains strict review for ordering/generated-ID effects and one QA-supported SY/PT difference; fresh-state acquisition and preparation outside the preserved-input profile |
| `snomed-us-snapshot-inputs-v1` | Explicit Snapshot roles, dates/headers/module dependencies, metadata/ICD inventory, mapping decisions and range evidence; actual March conversion matches all five official outputs and passes independent verification | Operational MRDOC/state producers and separately reviewed unsupported variations |
| `mth-prepared-inputs-v1` | Eleven prepared RRF roles, eight metadata roles, immutable prior CUI map, dispositions/VSAB choices, separate publisher/inserted history, canonical templates and identity validation; actual 2024AA input/reference closure verified | 2024AA conversion/comparison complete; nine explained files require explicit acceptance policy review; upstream preparation and operational transition evidence |

Fresh backend state capture for NCIt retains all six existing capture-assurance blockers; declaration flags cannot approve deployment, exporter, project, handler, completeness or coherent capture. This does not block consuming sufficient preserved preparation/state artifacts, as the August execution demonstrates. MTH does not require MetamorphoSys when its selected prepared bundle closes the declared history. Unknown source decisions and unsupported Full/Delta SNOMED stages do not get guessed defaults.

MDR and RADLEX retain their existing replay support and are registered in the new profile contract as pending adapters. Source registration alone does not enable execution or claim their source preflight has passed. Other sources can be added through reviewed profiles without changing the common field vocabulary.

The [native implementation](native-release-execution.md) records canonical packages, manifest-driven preparation/execution/validators and the actual dev evidence above. The [implementation plan](operational-release-gates.md) tracks the remaining NCIt review and MTH acceptance policy review. Synthetic variation tests do not substitute for a genuine additional archived release. Full conversions remain serialized on the existing dev worker, with the [retention policy](dev-retention-policy.md) and capacity gates preserved.
