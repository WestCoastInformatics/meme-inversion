# Reviewed NCIt QA and core shadow execution

The common native runner now admits `purpose: shadow` without an official current-release inversion. A separate reviewed NCIt QA policy also validates the exact historical Exposure correction in a disposable view. These capabilities are dev-only. Source algorithms, original conversion results and production remain unchanged.

## Shadow execution through the common commands

Use the same release manifest, source profile and configuration field names as historical native execution. Change `purpose` to `shadow`, omit `configuration.replay`, and remove every `reference-inversion` artifact. Inputs still require the source profile's complete publisher/prepared data, saved state, explicit inserted predecessor, history, reviewed decisions and allocation evidence. No current official output may be used as a constructor dependency.

Declare a planning budget in the selected `environment-profile` artifact's `data.shadow_resource_budget`:

```json
{
  "review_status": "reviewed",
  "review_id": "release-specific-capacity-review",
  "basis": "Recorded input sizes and reviewed output/scratch estimates",
  "output_bytes": 8589934592,
  "scratch_bytes": 17179869184
}
```

Those numbers illustrate the fields; they are not approved universal estimates. Record the actual review and estimates for the selected release. The worker keeps the existing source capacity floors, memory gate and disk reserve, and adds materialization, output and scratch estimates to its capacity calculation. This is admission planning and output-size validation, not a hard filesystem scratch quota. Emitted-only historical ID bounds cannot authorize a shadow run; a declared reserved range remains required.

```sh
python3 -B tools/inversion_request.py resolve-release shadow-release.json \
  --run-id shadow-source-release-001 --output shadow-release.lock.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  inspect-current shadow-release.lock.json --output previous-source.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  activate-runtime shadow-release.lock.json --output runtime-activation.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  submit shadow-release.lock.json --previous-receipt previous-source.json \
  --output launch.json
```

Use fresh run IDs and output filenames. The same dev host/account guard, pinned Git package, 169-file runtime verification, preservation receipt, physical input checks, network-isolated native stages and runtime serialization apply. `status`, `collect` and `verify-native` use the same common interface.

Clean conversion and validation produce `SHADOW_VALIDATED_COMPARISON_PENDING`. Every output has its candidate hash, with `reference: null` and `exact_match: null`. Acceptance remains false, comparison remains incomplete, and production eligibility remains false. Failed physical validation or an exceeded output budget produces `SHADOW_VALIDATION_FAILED`. Fresh retained-file verification can return `PASS_SHADOW_RETAINED_VERIFICATION`; that verifies the retained shadow evidence and still does not assert an official match.

## Attach the later official inversion

Once staff's official pre-insertion output exists, provide one `reference-inversion` artifact using the existing artifact schema. It must identify the same source/version, declare `data.reference_stage: inversion-src` and cover every planned output role with complete SHA-256/byte identities. The [archived manifests](native-release-execution.md#genuine-archived-release-manifests) contain examples of that artifact. Use proved pre-insertion `attributes.orig` where insertion later augmented `attributes.src`.

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  compare-shadow shadow-release.lock.json \
  --reference official-reference-artifact.json \
  --comparison-id comparison-source-release-001 \
  --output shadow-comparison.json
```

The operation independently verifies reference bytes, frozen inputs/code/runtime, planned links and all candidate outputs. It binds the exact original result hash and creates a separate child receipt. A missing standard archive cache can be downloaded through the existing reviewed download-only helper; no completed official tree is restored into the candidate. Candidate, prior and replaceable release-folder paths cannot serve as the oracle. No conversion repeats and the original pending result stays unchanged.

The child returns `PASS_EXACT` only when every complete output matches and physical validation remains clean. Other differences remain `DIFFERENCES_REQUIRE_REVIEW`. Failed operations retain a failed child status. This increment does not yet connect late comparison receipts to the separate corrected-difference acceptance policies, or to archive-backed shadow cleanup. Those operations currently refuse unsupported use rather than infer acceptance or preservation evidence.

## Reviewed historical NCIt QA

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock \
  review-native historical-nci.lock.json \
  --policy nci-reviewed-qa-v1 \
  --qa-decision docs/inversion-review/release-manifests/nci-2026-08e-qa-adjustment.json \
  --review-id acceptance-nci-qa-001 --output acceptance-review.json
```

This historical policy binds the exact reviewed decision, original lock/result, five publisher inputs, metadata, archived QA finding and complete official output identities. Only the declared termgroup field of the one exact row can change, in a temporary classes file. All five post-QA outputs pass complete structure/identity/reference validation. Classes, relationships and merge facts must match byte-for-byte; contexts must preserve every row and duplicate count; attributes may differ only in the proved generated-ID/context ordering effects, with positive unique IDs, identical ID sets, valid digests and exact ordered non-CONTEXT records. Generated-ID endpoint references prohibit that equivalence rule.

The separate accepted verdict is `PASS_WITH_REVIEWED_QA`, scoped to `temporary-post-inversion-QA-view`. The raw validation finding and original `DIFFERENCES_REQUIRE_REVIEW` remain unchanged. Scratch is removed on success or failure. The exact historical decision does not establish the editor's identity, create a generic DICOM mapping or authorize persistent `.src` rewriting. This policy does not accept a shadow lock; late-reference review integration remains separate work.

## Evidence and remaining work

The [increment evidence](qa-shadow-execution-20261112.json) distinguishes small native fixtures, common lifecycle fixtures with mocked conversion, committed CLI/frozen imports and the real historical dev QA review. A declaration-only shadow lock based on archived inputs does not establish a genuine predictive run. No new full inversion is part of this increment.

Next, complete the remaining source preparation decisions and run selected real shadow releases with their manifests frozen before staff output is available. Compare after staff publishes the official inversion, investigate every difference, and complete the late-reference review/retention handoff. Fresh state capture, operational QA/MRDOC, test insertion and MDR/RADLEX native manifest adapters retain their own gates.

## Adoption in the staff environment

After shadow and predictive runs are reliable for a source's supported workflow, promote its common configuration schema, Git templates/policy, runner and validators together into the staff-used environment on meme-edit. Start with common preparation/configuration, then a staff-observed inversion pilot for one source. Keep the existing staff workflow available during the pilot and move further sources as their evidence is ready. Preserve the standard disk layout unless a location change is explicitly agreed.

Staff acceptance includes clear configuration examples, reviewed optional additions, explicit prior-version dependencies, QA decisions, recovery instructions and the normal archive lifecycle. Production access, allocation, QA/MRDOC and insertion must be verified for the promoted workflow; dev success alone does not satisfy them. An optional skill can guide operators and troubleshooting through these deterministic commands. Reviewed configuration and executable validation continue to control the resulting files and acceptance.
