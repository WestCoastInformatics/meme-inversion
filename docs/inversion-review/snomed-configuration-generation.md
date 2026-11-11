# SNOMED configuration preview

November 10, 2026: the offline SNOMED adapter renders `etc/sct.cfg` from the existing common configuration, content-addressed case artifacts, and captured template bytes embedded in a frozen common lock. The historical September result is byte-exact to the meme-edit capture, SHA-256 `56b214ee51d698f716a1701ca387543ac161baf8f1618c9a5f51f044147465b3`. This records the original configuration-preview result. The follow-on [generated-settings execution](generated-settings-execution.md) uses a separately frozen native case; its actual outcome and verification are recorded there.

The shared preview dispatcher invokes `tools/snomed_configuration.py:preview_from_lock(lock)`. Its source-specific pure API is `generate(configuration, artifacts, template)`. The adapter returns the same recipe conventions as NCIt: `profile`, `files` with relative paths, `mode: 0o444`, hashes and base64 bytes, and explicit input `bindings`. It reads no live server, working-tree template, database, or output directory. The returned recipe sets `execution_enabled` and `production_eligible` to false; an existing replay lock's permission to run the older case is not permission to execute this generated-settings variant.

## Parameter translation and actual consumers

| Common field | Captured setting or consumer | Translation boundary |
|---|---|---|
| `source` | `RSAB` and source-qualified templates | Exact registered key `SNOMEDCT_US`; cross-source configuration is rejected. |
| `version` | `VSAB`, `EngNum`, versioned `VSY.0` name | One validated calendar date supplies the VSAB, release date and English US-edition title. `VSAB18` retains `<VSAB>`. |
| `replacement_baseline` | `VSABOLD`, `EngNumOld`; preserved source metadata | Explicit earlier version, not a calculated previous publication. `VSABOLD` expands configured `Merge.SELFNAMING2.sgQual1` and `Merge.SB.sgQual2`. The inspected core does not construct those two templates, so their existence does not prove a current core dependency on prior release files. |
| `comparison_baseline`, `publisher_history` | No selected core change-detection/history stage | This preview requires explicit null and an empty array, matching the reviewed case. It does not silently use replacement as comparison or infer additional history. |
| `inputs.source_data`, `.source_data_stage` | Fourteen required RF2 inputs used by `invert_rf2.pl` | One publisher-stage Snapshot manifest, exact filename-to-role association, file identities and current release agreement. Full input is rejected. |
| `inputs.reference_ncimeta` | `sources.src`, `termgroups.src`, `File.INP.ICD10META`, `File.INP.ICD10CMMETA` | Bind the four preserved preparation artifacts separately from native RF2. ICD target inventories are actual conversion inputs, originally prepared from MRCONSO. Metadata generation and live database queries are outside this preview. |
| `inputs.identity_state` | No prior identity-map consumption in inspected core | Explicit null. The core uses current native SCTIDs and the preserved source metadata. `ROOTSCUI`, `MakeRoot=0` and source-root representation stay in captured policy. |
| `inputs.source_plan` | Reviewed transition artifact | Replacement/comparison/history must agree exactly with the common configuration. This is not a new arbitrary metadata-decision schema. |
| `source_atom_ids` | `SaidStart`, `SaidEnd`; shared ID generator | The entire historical range must agree with the pinned captured configuration and its provenance artifact. This is not a new production allocation or a proved emitted-ID range. |
| `engine_ref`, `policy_ref` | Exact captured source engine and representation policy | Only the reviewed production capture is supported. The cfg template hash is separately fixed; changing or rehashing arbitrary template bytes is rejected. |

All other settings, including TTY, US language preference, concrete-value ATNs, RELMAP/inverses, refset patterns and qualifiers, retain their captured bytes. The preview does not adjudicate semantic policy disagreements or change transformations. It generates configuration only; no release-folder executable is used as a copy-forward source.

## Dependency closure and retained restrictions

The accepted case's eighteen files consist of fourteen RF2 files, two ICD target inventories and two source metadata files. Their pinned identities must also agree with the legacy contract in the common lock. The metadata manifest contains file hashes, not the row bytes; this adapter does not independently assert field-2 baseline correctness or installed-root/termgroup existence. Existing staging checks validate the preserved metadata before the old execution case runs. New release readiness needs an appropriate frozen metadata/state bundle.

`File.INP.STATEDRELS`, `File.INP.OldSubset` and `File.INP.URCid2Did` are not consumed by the inspected core. Consequently `EngNumOld`, which names the unused old subset, does not establish a dependency on an old source directory. `File.INP.COMPLEXMAPS` is different: code conditionally opens it, but the file is absent in this historical case. The preview preserves that declared absence; a newly present ComplexMap file requires a reviewed dependency change.

The filename validator is deliberately restricted to the captured `SnomedCT_ManagedServiceUS_PRODUCTION_US1000124_<date>T120000Z/Snapshot` package convention and the fourteen reviewed member names. It rejects alternative timestamps, package conventions, editions and extra inputs. It does not yet derive arbitrary package roots and member naming from publisher manifests. The synthetic later-release fixture verifies explicit replacement choice and parameter rendering within this same restriction; it proves neither acquisition nor execution of a future release.

The lock adapter accepts only the reviewed `SNOMEDCT_US_2026_09_01` case. It verifies the frozen source/configuration inventory, re-renders the recipe and retains the historical stage boundary. Insertion-time semantic types remain outside conversion; the official core comparison still uses the explicitly selected `attributes.orig` reference rather than enriched `attributes.src`.

## Preview verification and native execution

Run `python3 -B tools/check_snomed_configuration.py`. The 56 source-specific fixtures verify the independent captured bytes and every effective property, multiline mappings, immutable input handling, JSON round trips, eighteen-file dependency closure, explicit nonadjacent replacement, ID evidence and negative input/template/lock mutations. [Fixture evidence](snomed-configuration-preview-fixtures-20261110.json) distinguishes these local tests from full native replay.

The separate `snomed-properties-v1` execution profile freezes the generator/template identity, stages the generated cfg read-only through the common worker, and verifies it before preparation, conversion, cleanup and final comparison. The [execution record](generated-settings-execution.md) identifies the native run, official five-file comparison and independent retained-file scan. Every identifier, qualifier and duplicate remains in the comparison. The original preview profile remains non-executable, and historical nongenerated cases keep their identities. Full inversions remain serialized under the global runtime lock; no extra worker environment is introduced.
