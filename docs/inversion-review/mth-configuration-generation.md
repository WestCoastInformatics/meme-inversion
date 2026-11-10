# MTH/UMLS compatibility configuration preview

The parallel terminology development track implements a bounded, offline preview for the reviewed `MTH_2026AA` prepared-input transition. It renders the final range and effective legacy specs from the same common configuration fields used by NCIt and SNOMED. Both the original and corrected historical engines are supported independently; neither accepted case or its execution evidence is changed.

The implementation is [mth_configuration.py](../../tools/mth_configuration.py). `preview_from_lock(lock)` consumes the saved common lock's configuration, artifacts and frozen source files. It never selects a producer from the current filesystem. `generate(config, artifacts, templates)` is the pure deterministic translation function. The common preview frontend verifies the saved lock and records the separately identified preview generator; a historical lock is not relabeled as though it executed this generator.

## What the preview produces

Seven compatibility/data-policy files use the existing operational relative paths:

| File | Derivation |
|---|---|
| `range3.spec` | Complete common ID bounds, with the captured two-SRC-atom offset |
| `src/inv1.spec` | Frozen selected engine's atom/map spec, with the common version's `SourceDir` |
| `src/inv2.spec` | Frozen selected engine's attribute/relation/merge spec, with `SourceDir` and `MTHSAB` |
| `src/inv3.spec` | Frozen bequeathal spec, with explicit selected historical release predicates |
| `ncisources.spec` | Preserved reviewed source-disposition data, validated and exposed as structured decisions |
| `sab.vsab.map` | Preserved reviewed publisher-to-NCImeta version mappings |
| `src_data` | Preserved MTH SRC root declaration |

The four generated specs match the independently frozen effective configuration byte for byte. The saved policy data files also match their frozen identities. Every output carries a SHA-256 and `0o444` mode for the common frontend to materialize. No executable script, official generated inversion output, or prior-release executable is emitted by the preview.

The captured source plan has 201 source/version rows and 44 VSAB mappings. Different versions of one RSAB can have different decisions, such as an excluded older SNOMED version alongside the selected updated version. The parser retains this distinction, validates `KEEP`, `UPDATE`, `NEW`, `EXCLUDE`, `REMOVE` and `SPECIAL`, and rejects unresolved dispositions, duplicate source/version identities, multiple active versions for one RSAB, and unknown exclusion qualifiers. Reading and preserving these decisions does not implement new-release disposition discovery.

## One vocabulary with distinct baseline roles

| Common input | Actual MTH consumer or meaning |
|---|---|
| `version` | Current `MTH_2026AA`, its `SourceDir` and `DefineConst\|MTHSAB` |
| `replacement_baseline` | Last MTH version inserted into NCImeta; captured `old` link and prior `src/cui_said_map` |
| `comparison_baseline` | Separate optional change-detection input; explicitly null for this historical core case |
| `publisher_history` | Additional explicitly required publisher packages; explicitly empty because this preserved subset already contains the required history inputs |
| `inputs.source_data` and `.source_data_stage` | One frozen eleven-file prepared subset, not a new MetamorphoSys run |
| `inputs.reference_ncimeta` | Eight preserved metadata/decision files consumed by the historical core recipe |
| `inputs.identity_state` | Prior archive and nonempty CUI identity map belonging to the replacement version |
| `inputs.source_plan` | Frozen reviewed historical transition; saved disposition/mapping files are separately hash-bound policy inputs |
| `source_atom_ids` | Inclusive permitted range and captured allocation evidence; no live reservation |
| `source_options` | Empty for prepared-input replay; publisher/MetamorphoSys options are rejected |

The captured `prev` link and `invert1.s` setting `prevrel=2025AB` describe publisher-previous preparation state. They have their own provenance in `bindings.publisher_previous`. The captured `old` link is independently checked against the replacement CUI map. Both happen to identify `MTH_2025AB` in this case; this does not establish that their meanings are interchangeable.

The source script uses `prevrel` when selecting moved AUIs, CUI merges and MRCUI bequeathal rows. Handling an intervening publisher release that was not inserted requires an explicitly reviewed history-selection recipe. This preview rejects changed versions, replacement baselines, comparison/history selections and publisher-stage requests rather than deriving them from a calendar or from whichever folder supplied code.

For the historical complete range `769443591..773943592`, translation gives:

```text
SRCbuilder -s            769443591
SourceAtomIdBase         769443593
SourceAtomIdLimit        773943592
first ordinary atom     769443594
```

The final line follows the actual `autoinv.pl` consumer, which increments the base before emitting an ordinary atom. Changing range bounds invalidates the captured range evidence; estimation and production reservation remain separate stages. No preliminary `bigrange.spec` run is generated here.

## Verification and remaining gate

Run `python3 -B tools/check_mth_configuration.py`. The 68 checks include independent captured Git file goldens for both engines, common configuration and saved-lock agreement, JSON round trips, input immutability, incomplete or rebound metadata/native/identity inputs, source-disposition errors and separate `old`/`prev` failures. An actual frozen Perl consumer processes a tiny input with the generated atom spec and range, proves the emitted ID and verifies range exhaustion. Only `SourceDir` is relocated into the temporary test fixture.

The [fixture record](mth-configuration-fixtures-20261110.json) distinguishes these local fixture executions from a complete native inversion. The next execution gate is a separately identified, serialized dev replay using the generated settings, followed by the existing official comparison and native-derived correction audit. No full inversion, MetamorphoSys run, source metadata regeneration, database QA, ID reservation, insertion, deployment or operational release approval is performed by this preview. General new-release preparation remains later work.

## Generated settings in the native prepared-input runner

The separate `mth-prepared-spec-v1` execution profile connects those seven settings/data files to the existing final-range prepared-input runner. The original `mth-prepared-spec-preview-v1` profile and historical nongenerated cases retain their identities and behavior. A generated recipe describes construction inputs; the actual native outcome belongs to its separately identified worker result.

The resolver calls `execution_recipe(configuration, case, code_files)` before completing the common lock. A reviewed case must explicitly select `configuration_generation: {"profile": "mth-prepared-spec-v1"}`. `execution_recipe_from_lock(lock)` rechecks the frozen case identity and exact recipe after resolution. Both builders continue to distinguish original from corrected source-engine policies. Common case registration, correction-audit enforcement and final lock verification remain the responsibility of the common resolver/worker.

The native package transports two fields:

```text
generated_configuration          complete frozen execution recipe
configuration_generation_inputs  {configuration, artifacts}
```

The existing pinned `code_files` inventory supplies template producers and independent historical hash oracles. During preparation, `stage_code_files` skips the seven corresponding descriptors in its source-copy path and writes their generated recipe bytes with exact `0o444` modes. It preserves the original descriptors unchanged, including their original modes, as evidence. All other source code and captured link topology follow the existing Git staging path. Metadata/native packages and the replacement CUI map remain separate inputs and are checked against the generation bindings before staging.

`verify_generated` recomputes the recipe and verifies all seven file hashes and exact modes. It rejects writable files, changed read-only modes, modified contents, symlinks and mismatched dependency bindings. Full `verify_inputs` calls this gate before conversion and after comparison. Preparation and native results retain the compact `configuration_generation` receipt, including recipe hash, generated file inventory and all construction bindings. The SRCbuilder argument comes from the recipe's independently checked allocation binding when generation is selected.

Run `python3 -B tools/check_mth_generated_execution.py` for the [57 generated-execution fixtures](mth-generated-execution-fixtures-20261110.json). They exercise actual staging and actual staged Perl consumption, saved-lock and package mutation rejection before candidate writes, read-only verification before/after the fixture conversion, and the unchanged nongenerated staging route. The existing 68 preview fixtures and 62 replay/case-lock/identity/correction-audit checks also pass.

These local fixtures do not claim a new full MTH inversion. The generated case still needs its serialized dev execution, official output comparison and existing native-derived correction audit before its native acceptance can be recorded. No live database access, production allocation, insertion or deployment is introduced by this runner extension.
