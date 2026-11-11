# Next gates for operational release preparation

The historical framework establishes reproducible inputs, pinned Git code, generated compatibility settings and independent output checks. The next phase should admit a new release through reviewed data contracts. Keep the characterized converters and the existing dev layout while adding that preparation layer. Source registration or a successful historical comparison cannot authorize an arbitrary new release.

The common configuration vocabulary remains unchanged. Release-specific precision belongs in the contracts for `inputs.source_data`, `inputs.reference_ncimeta`, `inputs.identity_state`, `inputs.source_plan`, `publisher_history` and `source_atom_ids`. Code comes from Git; an older release contributes only declared data and identity state. An archived complete prepared-input bundle is a valid starting point, without rebuilding its original database queries.

## Implementation order

| Order | Deliverable | Acceptance gate |
|---|---|---|
| 1 | Release-plan and input-bundle preflight for each source | Every dependency has an identified producer, release/stage and hash; missing decisions and inconsistent state block a shadow run |
| 2 | Verified installed-state capture where the selected transition requires fresh state | Deployed application/exporter identity, project, complete export scope and a coherent state boundary are established; preserved historical inputs remain usable directly |
| 3 | Reviewable discovery of new source values and metadata | New subsources, termgroups, relationship types, source dispositions and ranking choices are explicit data decisions; no silent guessed defaults |
| 4 | Real allocation and a newly registered dev case | Final inclusive ID bounds have allocation evidence, all settings are generated, and code/policy/input identities are frozen before execution |
| 5 | Serialized shadow inversion and release-specific acceptance | Full outputs and retained identity state pass independent checks; historical correction exceptions are not broadened to fit the new release |
| 6 | Operational QA, test insertion and controlled adoption | Required database QA/MRDOC and insertion checks pass before a release becomes eligible for staff use or production insertion |

Capture overlapping NCImeta state once per verified consistency boundary and let source adapters render their required legacy metadata files. Avoid separate live-query paths that silently take roots, versions and precedence from different moments. A new release should be admitted through reviewed configuration/artifact data, rather than by editing release constants in copied scripts. Keep historical cases bounded while developing that admission path.

Run preparation/discovery locally in parallel where useful. Continue serializing full conversions and shared-runtime changes on the existing worker. Separate worker environments should follow demonstrated contention or incompatible requirements.

## NCIt

The [source-plan pilot](nci-source-plan.md) already represents optional subsource and termgroup additions, including empty addition lists and catalog promotion. A skipped month changes the explicit replacement baseline, not the configuration format. A fresh transition needs verified installed roots and ranking state, a reviewed representation catalog and decisions for newly encountered native values.

The [backend discovery](nci-backend-state-discovery.md) establishes important capture requirements: inverter SAIDs are source alternate identifiers rather than generated database IDs; root selection uses individual SRC/RPT atoms with `V-<RSAB>` codes; default and project precedence are separate ordered RSAB/TTY lists. Direct atom responses may omit alternate identifiers. A complete, deployed exporter and coherent capture boundary remain to be demonstrated. The earlier versioned-termgroup synthetic preflight must not be treated as operational ranking proof.

Resolve the declared `CTCAE 6.0` mapping and external ranking findings through reviewed source decisions. Do not modify historical comparison rules to conceal them. See [state acquisition gaps](nci-state-acquisition.md).

## SNOMEDCT_US

Introduce a Snapshot package manifest and discovery report before generalizing the [bounded generator](snomed-configuration-generation.md). The current profile fixes the historical US edition, package naming and fourteen RF2 members. A new manifest should bind the actual package/member paths, headers, checksums, release identity and compatible module dependencies. Snapshot rows legitimately contain earlier effective dates; they need not all equal the package date. Alternate packaging or newly required members need review rather than filename guessing.

Keep the last-inserted SNOMED baseline separate from the frozen NCImeta metadata/inventory bundle. Saved `sources.src`, `termgroups.src` and ICD inventories suffice for the characterized replay. Recreating their historical exports from today's database is optional upstream coverage. The current converter opens the ICD inventories, but direct pairwise mapping emission is commented out; do not claim they currently generate those relationships or drop the dependency without an explicit impact review.

Discover relationship/refset identifiers, changed labels, term types and attribute patterns before the long conversion. Native mapping currently depends on names resolved to type IDs, and unknown relationship types can become `XX-<typeId>`. Reviewed mappings should identify stable SCTIDs/refset IDs and explicit REL/RELA/inverse decisions. Existing association-policy and inverse-name documentation conflicts need adjudication before a semantic change.

Operational MRDOC generation also needs a frozen RELA-inverse, expanded-form and TTY-class snapshot and reviewed overrides. The captured wrapper deletes and regenerates documentation while the generator makes three live metadata calls. Preserve those inputs as artifacts and remove manual comment toggles through a separately tested preparation change. [Captured wrapper](../../sources/SNOMEDCT_US_2026_09_01/bin/invert.s), [converter](../../sources/SNOMEDCT_US_2026_09_01/bin/invert_rf2.pl)

## MTH/UMLS

Start with a reviewed release-plan/input-bundle preflight. A final conversion can consume a staff-produced, frozen prepared subset, metadata bundle and last-inserted CUI identity map. The characterized bundle has eleven RRF inputs and eight metadata roles. Validate its release, producer, dispositions and dependency closure; MetamorphoSys regeneration is needed only when the bundle is absent or publisher preparation is explicitly selected. [Preserved-input contract](mth-2026aa-input-output-contract.json)

Promote `ncisources.spec`, `sab.vsab.map` and `src_data` decisions into typed release artifacts, retaining source/version identities, rationale and hashes. Guessed `KEEP`/`UPDATE`/`NEW`/`EXCLUDE`/`REMOVE`/`SPECIAL` values are proposals requiring review. The current common plan identifies the historical transition; it does not discover new dispositions. [Disposition preparation](../../sources/MTH_2026AA/preinvert1.s), [proposal script](../../sources/MTH_2026AA/guess.ncisources.spec.pl)

Generalize the distinction between last inserted MTH (`old`) and publisher-previous preparation state (`prev`). The historical case uses 2025AB for both. An intervening uninserted publisher release requires an explicit history-selection recipe applied consistently to moved AUIs, CUI merges and bequeathal predicates. Do not repoint a generic previous-version link and assume the transition is correct. [Initialization](../../sources/MTH_2026AA/initdir.s), [first pass](../../sources/MTH_2026AA/invert1.s)

Fresh preparation needs the relevant saved `current_sources` and `precedence` exports, not a reconstructed entire database. Preserve their snapshot identity and verify newly introduced rankings. Keep preliminary estimation separate from final allocation; changing the final range requires rebuilding dependent maps and outputs. The corrected retained-atom identity rule remains applicable, while the exact 2026AA correction audit is deliberately bounded to that historical case. New releases require their own reviewed acceptance, using generic identity validators rather than widened historical waivers. [Metadata preparation](../../sources/MTH_2026AA/preinvert2.s), [metadata builder](../../sources/MTH_2026AA/make.sourcestermgroups.pl), [correction contract](mth-correction-audit.md)

Two captured preparation defects need separate fixes and fixtures before reusing those scripts for new releases: `preinvert2.s` checks the disposition in field 2 although it is field 3, and `guess.ncisources.spec.pl` uses assignment in its `SPECIAL` branch. Neither defines release readiness. They are outside the prepared-input native replay and have not been changed here.

## MDR and RADLEX

Retain their accepted historical common requests and regression coverage. A future release uses the same preflight, artifact identities, allocation and acceptance gates, with its own reviewed source contract. Infrequent execution is no reason to infer settings from the last folder. RADLEX's observed historical emitted-ID bound still does not prove a production reservation end. [Existing contracts](additional-source-contracts.md)
