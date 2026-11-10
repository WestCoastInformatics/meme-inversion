# Parallel terminology configuration development

The November 10, 2026 development increment assigns NCIt, SNOMEDCT_US and MTH/UMLS to separate agents and Git worktrees, with one coordinator integrating the common interface. The starting revision is `31539b6`, on the production-derived `test/inversion-replay-toolbox` history. Earlier automation prototypes do not define this implementation.

The three tracks use the same [common configuration](configuration.md). They do not create separate names for version, replacement baseline, publisher history, input stage, identity state or complete source-atom ID bounds. Genuine differences remain explicit source contracts. MDR and RADLEX remain registered and executable through their existing reviewed historical adapters; recognition does not imply a new settings generator.

| Track | Development boundary | Evidence required |
|---|---|---|
| NCIt | Offline release preflight using an explicit, content-bound installed-state snapshot and the reviewed source plan | Distinguish known representation from installed roots/termgroups; retain historical findings; reject missing/inconsistent state |
| SNOMEDCT_US | Offline compatibility-configuration preview from the common configuration and pinned captured settings | Exact historical effective settings; Snapshot input/dependency closure; explicit replacement and complete historical ID bounds |
| MTH/UMLS | Offline specification/settings preview using the prepared-input contract and pinned templates | Exact historical specifications; source decisions and identity files preserved as declared data; publisher history distinct from inserted baseline; real Perl ID-offset check |
| Coordinator | Common preview command, recipe safety/provenance, integration and five-source compatibility | Existing reviewed locks remain valid; no cross-source option leakage; immutable inputs and read-only outputs |

## One preview interface

Resolve an existing reviewed request using the [common interface](common-interface.md), then preview through one command:

```sh
python3 -B tools/inversion_request.py resolve docs/inversion-review/request-examples/snomedct_us-as-produced.json --run-id snomed-settings-preview --output snomed-settings.lock.json
python3 -B tools/inversion_configuration.py snomed-settings.lock.json --output-dir snomed-settings-preview
```

The same preview command consumes the MTH historical locks and the NCIt `generated-configuration` / `source-plan` locks. Older NCIt characterization cases and MDR/RADLEX have no adapter in this new preview command; their existing replay operations remain available. The command requires the isolated Python environment from the common interface. It creates a fresh directory containing read-only generated files and `configuration-preview.json`; it never stages the candidate into the worker's operational source tree.

The receipt binds the original lock, source engine, runtime, recipe and the actual current preview-generator file hashes. The historical lock's apparatus identity remains the original one. An uncommitted generator has a null generator Git reference rather than being mislabeled as committed code. Payload hashes, paths, duplicate destinations, file/directory collisions and read-only modes are checked before writing. Existing destinations are not reused.

NCIt's optional installed-state preflight uses `--installed-state SNAPSHOT.json --installed-state-sha256 CANONICAL_JSON_SHA256`. The hash must be taken from the reviewed frozen snapshot manifest, not silently calculated as a substitute for expected identity. This preview evidence does not replace the historical lock's metadata model or claim to reconstruct the historical database. The receipt retains the preflight findings; a blocked preflight exits with status 3 after retaining its preview. Invalid input exits with status 2 before output publication. See the source-specific guide for the snapshot contract.

## Convergence and execution

Each track owns source-specific tools, fixtures and documentation. The coordinator owns common schema, resolver, worker, registry and this preview interface. Source agents preserve captured code and accepted case identities; they do not introduce semantic fixes or new execution eligibility through a preview. Source-specific commits are reviewed and integrated into the consolidated working branch, while original production and accepted native-run revisions remain intact.

Separate worktrees allow local source fixtures to run concurrently. Full inversions on `ncias-d3777-c` continue to use the existing global runtime lock and mirrored operational paths. No separate workers, alternate disk layouts, runtime activation, production changes or new full inversion runs are part of this offline increment. Additional worker environments remain deferred until measured demand justifies them.

Passing preview fixtures proves the bounded translation and validation behavior described by each source contract. Before a preview becomes an execution path, register and freeze the reviewed generation contract, stage only declared inputs, run that generated configuration through a serialized dev inversion, and compare all outputs against its frozen official reference. Operational new releases additionally require appropriate installed state, reviewed source decisions, production ID allocation, legacy QA and insertion approval. Existing historical native-run evidence is not relabeled as a test of these new preview adapters.

## Completed checks and next execution gate

The [convergence report](configuration-convergence-20261110.json) records 472 passing checks: common historical interface 89, worker 27, existing NCIt generator 37, NCIt source-plan lifecycle 52, NCIt installed-state preflight 49, SNOMED preview 56, MTH preview 68 and common preview 94. Source fixtures ran concurrently in isolated worktrees; the integrated common suite then validated all nine historical case variants across all five sources. This does not imply simultaneous native inversions.

The [SNOMED preview](snomed-configuration-generation.md) is byte-exact to the captured September configuration, including all representation mappings. It retains the captured US1000124 / T120000Z package convention; arbitrary package naming is not covered. The [MTH preview](mth-configuration-generation.md) emits seven files byte-exact to their historical settings, exposes 201 preserved source decisions and 44 VSAB mappings, and verifies the allocation offset with the captured Perl consumer. It does not generate a fresh MetamorphoSys subset or infer new source dispositions.

The [NCIt preflight](nci-release-preflight.md) uses synthetic installed-state fixtures to prove its checks; no real database snapshot was acquired. Both historical findings remain blocking even when a snapshot establishes that an external ranking target exists: existence and approved ranking policy are different decisions. The common CLI retains a blocked report and exits nonzero.

Next, freeze a generated-settings execution case for SNOMED and run its dev inversion and official comparison; then do the corresponding MTH run with its mandatory correction audit. Those jobs use the existing serialized worker. In parallel, obtain reviewed installed-state evidence and resolve NCIt's mapping/ranking decisions. No source should move from preview to new-release execution merely because its historical settings match.
