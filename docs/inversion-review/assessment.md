# NCImeta inversion modernization assessment

Assessment date: November 3, 2026. Scope: NCIt, SNOMEDCT_US, and MTH/UMLS.

Scope extension, November 5: the common request/configuration interface must also accommodate MDR, RADLEX and future registered sources, including infrequent releases. They use the same common fields, with independently reviewed adapters and source contracts. MDR_29_1 and RADLEX_4_3 production workflows have now been inspected and their source code captured with provenance; their dev replays and acceptance profiles remain to be done. [Discovery contracts](additional-source-contracts.md) [Source registry](source-registry.json)

Replay priority clarification, November 5: complete preserved input bundles are sufficient for historical replay. Verify versions, hashes and dependency closure, then reproduce the official output from those inputs. Regenerating already-preserved metadata exports or prepared publisher subsets is additional coverage, not a prerequisite. Future operational runs should capture these inputs automatically. This avoids making reconstruction of an entire historical database or obsolete input-generation runtime a gate when the required answers/files are already archived.

## Recommendation

Adopt one release lifecycle with independently reviewed source adapters, explicit baseline dependencies, versioned representation rules, and independently validated output packages. Preserve the working Perl transformations initially. Move operational code out of release directories before replacing transformation logic, then replace components behind proven input/output contracts.

The first investments should establish an isolated replay/comparison apparatus, make validation trustworthy, and provide a controlled, versioned home for operational code. Candidate inversions must run on a development worker away from meme-edit so staff can continue actual inversions over the coming cycles. Multi-year S3 history and list/pull/push/update operations already exist. Use them to retrieve frozen official reference outputs and declared inputs rather than treating archival preservation or a replacement transfer system as a standalone leading project. Rewriting parsers before output acceptance and source semantics are established would move undocumented assumptions into new code without establishing that the results are correct.

Use an optional skill to help operators understand plans, resolve new metadata, and troubleshoot failures. The executable pipeline must own transformations, validation, restart decisions, and release eligibility. An operator, CI job, and a skill must invoke the same pipeline and receive the same result.

**Skipped NCIt months are a normal, required case.** October may replace August even when September was published or inverted. Neither a calendar calculation nor the directory from which scripts were copied identifies the correct replacement baseline.

The revised six priorities are:

| Priority | Work | Reason for its position |
|---|---|---|
| 1 | Isolated replay/comparison apparatus, trustworthy validation and release gates | Enables development without disrupting staff and detects incorrect or incomplete candidate output |
| 2 | Version operational code and remove copy-forward code state | Establishes controlled changes and eliminates a recurring source of drift |
| 3 | Explicit baseline/lifecycle orchestration using existing S3 tools | Selects the correct historical inputs and coordinates established restore operations |
| 4 | Consolidated metadata and representation rules | Removes manual generated-file edits and contradictory source decisions |
| 5 | Incremental transformation migration | Replaces components after their behavior and acceptance criteria are understood |
| 6 | Optional skill and simpler operator interface | Improves usability over the same deterministic execution and validation contracts |

The first NCIt replay supplies concrete priority-1 fixtures: an original-code FDA PT atom loses its term type through a reused template, and hierarchy hash iteration changes context order and generated attribute IDs. Both now have separate committed fixes and passing full October core comparisons: explicit PT (`0de8ca2`) and stable context emission (`bfda2ce`). Atoms/relationships/merges are byte-identical to the archive; context/attribute content matches under the declared order/ID profile. The ordering fixture also passes across four hash seeds locally and on dev. The unchanged baseline failure, PT-only outputs, and old library remain preserved. The user accepts a manual post-QA PT correction as the working historical explanation; operator confirmation remains nonblocking. [Completed NCIt comparison](nci-reference-boundaries.md#completed-core-comparison), [ordering result](nci-2026-10d-context-order-summary.json)

Priorities 1 and 2 should start together; validation fixes and the test apparatus must themselves be version controlled. The first full case should replay unchanged legacy code on the development worker against a frozen official S3 reference before evaluating rewritten code. Representative S3 restores support that apparatus and priority 3; they are not a new archival program. The separate [test architecture](test-architecture.md) specifies worker isolation, the request format, case locking, reference-stage selection, ID-aware comparison, and acceptance criteria.

Use [one common configuration model](configuration.md) across every registered source from the start. Shared fields have the same name and meaning; distinct baseline roles remain separate, with a small typed section for genuinely source-specific options. Generate legacy settings through adapters initially, then let migrated components consume the common model directly.

## Implementation starting point: operational code on meme-edit

The user has explicitly selected the operational code on **meme-edit as the authoritative starting point**. Start a fresh implementation effort from a verified snapshot of that deployment: shared libraries, the source-specific scripts actually used by staff, specifications, mappings, defaults, environment/runtime requirements, and existing archive-tool dependencies. Capture hashes and provenance and establish that snapshot in Git before making modernization changes.

The previous inversion-rework branches and automation wrappers are background evidence only. They are not the implementation base, an inherited architecture, or a required workflow. Do not merge or cherry-pick that work as the foundation. The shared-library match to repository main does not establish that all deployed source-specific code is already represented there; verify each operational component against the production snapshot.

The assessment collection came from `ncias-q3793-c:/local/content/MEME/MEME5/inv`. A subsequent read-only capture of that user-specified deployment has now been imported into a dedicated local baseline branch and snapshot tag. Source provenance is the physical server tree; the meme-edit web hostname resolves to a load balancer. Code selection is supported by scripts/runbooks and observed execution/output artifacts, rather than a live installed-version database query. The snapshot is content-verified. On dev, native NCIt preparation reproduced all three archived TREF files byte-for-byte and core conversion completed. Comparison found one substantive termgroup difference, alongside context ordering and generated attribute-ID differences; the original baseline finding is resolved by the separately committed candidate, which passed its full October core comparison. See [the baseline result](baseline-result.md).

First reproduce the verified operational behavior on the isolated development worker, using matching official reference inputs/outputs. Then introduce the common configuration, lifecycle changes, validation fixes, and incremental replacements under comparison gates. For older historical cases, retain the exact archived production code when needed to distinguish historical release behavior from a candidate change. Production behavior is the compatibility reference; documented defects still require explicit reviewed corrections and independent correctness checks. Starting afresh does not require discarding working production transformations or rewriting every component at once. [E17](evidence.md#e17-user-selected-implementation-starting-point)

## Evidence and limits

The review combined the five supplied Word documents, server-resident source runbooks, deployed transformation and QA code, adjacent NCIt release differences, current filesystem dependencies, and the Git prototype. The two SNOMED Word documents share substantial material; their repetition is not independent corroboration.

The read-only server collection captured 1,228 filesystem entries and 292 code/configuration/documentation files under `/local/content/MEME/MEME5/inv` on `ncias-q3793-c`, plus supplemental collections of MTH metadata, dependency checks, and S3 integration code in `/local/content/MEME/MEME5/ncim/bin`. The latter review covered `list_s3.csh`, `pull_s3.csh`, `push_s3.csh`, and the archive-related portions of `backupIndexes.csh` and `test_insertion.sh`. Publisher datasets were inventoried rather than downloaded. All 39 deployed `INV/lib/*.pm` modules have the same SHA-256 values as their counterparts in the reviewed main checkout. This connects the shared-library findings to deployed code, rather than just the prototype.

Git main was `3be55ea33024ba9ef998207c1a6de9eb3e482a56`; the inspected `NM-271-inversion-rework` branch was `d65d9f60ce11046154b5439ab083b634460ad5b8`. That branch contains `run_nci_inversion.sh`. Neither the accessible branch listing nor available Git history contained `run_snomed_inversion.sh`; its implementation was not reviewed. The deployed SNOMED scripts were reviewed directly.

The initial review was a code, documentation, dependency, and selected-log assessment. Subsequent authorized dev work installed the pinned runtime, retained the official October S3 archive, and regenerated native intermediates. All three TREF files match exactly, and the unchanged core inverter completed offline against declared archived source metadata. The five-output comparison is complete: relationships/merges are byte-identical, contexts and attribute content match under the explicitly described ordering/ID diagnostics, and one atom lacks PT in its FDA termgroup. The fixed candidate subsequently passed its scoped core comparison; the original baseline failure is retained as evidence. No test insertion, database operation, or production change has been performed. See [current execution and coverage](nci-reference-boundaries.md#completed-core-comparison).

Detailed locators and conflicts are in [the evidence notes](evidence.md). Original file hashes, collection times, and dependency-check results are in [the evidence manifest](evidence-manifest.json).

The common test-service design and request/schema examples remain proposals. Source-specific characterization tools now execute and compare NCIt on the dev host; they are not yet a general runner. Official NCIt and SNOMED archives have been downloaded and frozen. No importer environment or test insertion has been executed.

The user subsequently selected the existing development host `ncias-d3777-c` and confirmed separate storage. A read-only preflight and S3 archive-metadata check have passed. Setup mirrors meme-edit's physical directory layout; path changes require an explicit design decision. Dev and production need not contain the same release-folder inventory: each run resolves only its declared versions and dependencies. See [development-worker readiness](dev-worker-readiness.md).

The shared-code/environment step has now been completed on dev: 169 files from the production snapshot were installed at `inv/INV` and `inv/ENV`, both shell environments verified, and selected NCIt script syntax checks passed without external networking. Existing source folders were not changed. The full replay apparatus and its reference inputs remain to be prepared. See [the setup record](dev-shared-runtime-setup.md).

The first October reference archive is frozen and the clean candidate has completed conversion and comparison. Saved October metadata explicitly names August as low source. Relationships/merges match exactly, context/attribute contents match under the documented ordering and generated-ID diagnostics, and one FDA atom has a missing PT term type. This is a reproduced generator defect requiring a separate candidate correction; the unchanged baseline is preserved. Archived `insert` history is outside the selected reference scope. [Completed comparison](nci-reference-boundaries.md#completed-core-comparison)

Historical reproduction has not been shown impossible. Some live queries affect output generation; others affect only QA. Saved exports or query responses can supply the historical values without a complete database clone. The first replay must audit the chosen archive and identify any actual missing inputs before drawing a conclusion about exact reproducibility. See [the historical replay distinction](test-architecture.md#historical-replay-is-not-presumed-impossible).

## What the three workflows actually do

### NCIt: publisher export, intermediate formats, and release-specific metadata

The deployed path starts with the publisher's declaration, hierarchy, and relation files. `create_rolegroups.pl` identifies groups containing multiple relationships. `create_tref.pl` converts the export into local TREF dialects; deduplication and `tref_2_relational_files.pl` produce additional files used for comparison and TDE QA. `invert_NCI.pl` uses the shared `NLMInv`, record writers, ID generator, and hierarchy implementation to produce `.src` files. `makeDoc.pl`, `srcQa.pl`, and conservation review follow.

There are two substantial sources of mutable state: source metadata copied from the previous inversion and code edited within the current release. Comparing September and October 2026 shows an actual semantic change, beyond date substitution: October enables `processSubsourceAtoms` and replaces a previous hardcoded subsource with BLOODPAC. The Word instructions explicitly require enabling that routine for a new subsource and disabling it afterward. That release decision belongs in reviewed metadata, with explicit scope, rather than in a copied script's comment state. [E3](evidence.md#e3-ncit-code-is-a-carrier-of-release-state)

NCIt's QA also depends on prior intermediate data. The deployed TDE checker reads `NCI_2026_09D/tmp/nci_roles3.tmp`, previous comparison outputs, and previous `orig` files. Those are real dependencies even though some live under directories named `tmp` or `archive`. The next release must receive a declared comparison bundle, not assume that a working directory still exists. [E2](evidence.md#e2-prior-data-and-archive-closure)

October's conservation notes explain low-source QA mismatches by saying September had not been inserted and the database still held August. This is evidence that inversion chronology and insertion chronology diverge. It is not sufficient evidence that September must eventually be inserted. For an intentional skipped-month update, October's replacement lineage must resolve to August; September can remain an optional comparison reference. [E1](evidence.md#e1-previous-is-not-one-relationship)

### SNOMEDCT_US: direct RF2 with NCImeta-specific representation

The deployed September 2026 configuration selects the US RF2 **Snapshot**, names all relevant terminology/refset files, and provides SAID bounds. `invert.s` also derives ICD target inventories from a separately versioned NCImeta `MRCONSO.RRF`, currently the `202608` release. Thus RF2 alone does not determine the output: the target terminology inventory is another input.

The September archive is now frozen on dev and all five archived code/configuration files match the production snapshot. Its original `src/attributes.orig` has 9,324,589 rows; final `src/attributes.src` is that exact byte prefix plus 1,133,725 SEMANTIC_TYPE records. The user confirmed that those are added during data insertion. Therefore the inversion comparison must map candidate `attributes.src` to archived `attributes.orig`, preserving its own original semantic-type record; insertion enrichment is separate coverage. Both archived ICD target inventories are present. [SNOMED boundary contract](snomedct-us-2026-09-01-input-output-contract.json)

The unchanged production SNOMED engine has now run on dev with those archived inputs, followed by the original dangling-attribute cleanup. **All five core files are byte-identical to the official reference**, including all 20,403,095 contexts and every generated ID. Conversion took about 25 minutes and peaked at 5.3 GiB resident memory. No prior source folder was restored; saved source metadata confirms March as the replacement baseline. The initial independent checker omitted valid SRC/VSY and ROOT_SOURCE_AUI tokens; production framework/type rules establish both. The original full scan is retained, and a separate review corrects only those classifications from its complete counters. This is exact core reproduction using archived metadata/ICD fixtures, not a full metadata/QA/insertion workflow replay. [Completed result](snomedct-us-2026-09-01-baseline-summary.json), [validator review](snomedct-us-2026-09-01-validation-review.json)

`invert_rf2.pl` processes metadata, concepts, attributes, definitions, language/subset data, descriptions, relationships, associations, maps, and contexts in a meaningful order. Concrete relationship values, language preference, relationship groups, and module names are already part of the source logic. Treating this as a generic delimited-file conversion would lose important semantics.

Unknown relationship mappings become `XX-<typeId>` values. The documented process asks the operator to discover them through an initial inversion, edit `SCT.RELMAP`, edit `MRDOC.RRF`, comment out the MRDOC regeneration section, and run again. The wrapper otherwise deletes/recreates that manually edited output. Replace that cycle with native-data discovery, reviewed relationship metadata, and repeatable MRDOC generation. [E4](evidence.md#e4-snomed-discovery-and-manual-metadata)

The documents describe both the former NLM-generated `.src` approach and the direct RF2 approach. They explain the independence goal but retain a historical statement that the local approach had not been used for a real inversion. The current server contains direct-RF2 scripts, outputs, and test/insert artifacts. The direct path should be the migration baseline; the old approach should remain a separately named historical/reference mode only if it is still needed.

Some representation decisions need explicit adjudication. The documents discuss retaining expected historical associations involving obsolete descriptions while dropping certain current-description cases; the deployed association loop requires active endpoints. The inverse-name examples also conflict between `_for` and `_of`, while the deployed configuration uses `procedure_approach_of`. Preserve observed behavior for comparison, but do not declare it the desired policy without domain review. [E5](evidence.md#e5-snomed-policy-conflicts)

Scale matters: the inventoried SNOMED `src/contexts.src` is **6,220,515,460 bytes**. Context generation, comparison, packaging, and validation need bounded-memory processing and explicit disk requirements. A more readable implementation that materializes every path in memory may be an operational regression.

### MTH/UMLS: selective synchronization with the existing NCImeta state

MTH is a stateful integration workflow, not simply another full-source parser. It combines the full UMLS package and separate full `MRREL.RRF`/`MRSAB.RRF` inputs, UMLS-to-NCI VSAB mappings, source dispositions, current NCImeta source/precedence inventories, MetamorphoSys subset/context generation, and prior CUI/AUI mappings.

`initdir.s` creates the new release and copies scripts/specifications from `prev`. `preinvert1.s` updates VSAB mappings and proposes `ncisources.spec`. `preinvert2.s` captures current NCImeta metadata, configures MetamorphoSys, and creates a derived subset. `invert1.s` builds preliminary atoms and estimates the required range. `invert2.s` rebuilds with the allocated range, derives AUI/CUI maps, handles moved atoms and CUI merges, emits attributes/relationships/bequeathal relationships, builds contexts, and prepares final files. Server-side process QA and insertion follow.

The distinction between `KEEP`, `UPDATE`, `NEW`, `EXCLUDE`, and `REMOVE` is central. A kept source can still participate in moved-AUI/CUI reconciliation; it cannot simply be omitted from all state processing. SNOMEDCT_US is explicitly excluded from the MetamorphoSys REST subset because it is handled separately. These ownership decisions must survive any common framework. [E6](evidence.md#e6-mth-is-a-stateful-source-plan)

MTH also changes the publisher package in place: `updatevsabs.s` rewrites MRSAB inside the `.nlm` archive, copies the rewritten data elsewhere, and marks completion with a sentinel file. The sentinel does not identify the mapping-file version that produced it. The Word guide's recovery advice can escalate from removing the sentinel to deleting/rebuilding the whole directory. The replacement should retain immutable native files and produce a separately identified derived package. [E7](evidence.md#e7-mth-mutates-upstream-inputs-and-uses-weak-checkpoints)

## Principles for resolving conflicting instructions

Do not choose an instruction because it appears in the greatest number of documents, contains the most recent example month, or is implemented by the newest wrapper. Record four separate things: observed behavior, documented intent, the proposed rule, and who must resolve any remaining ambiguity.

| Principle | Evidence supporting it | Design consequence |
|---|---|---|
| Publisher chronology and NCImeta insertion chronology differ | Both SNOMED guides; MTH script comments; NCIt conservation notes; user's skipped-month clarification | Explicit replacement baseline independent of publisher/comparison history |
| Representation decisions are unavoidable | Basic guide's format-change review; SNOMED relationship decisions; MTH dispositions; NCIt new subsources | Versioned source policies and explicit review of newly encountered values |
| An exploratory run is different from a release build | Basic guide; SNOMED two-run procedure; MTH preliminary/final ID passes | Discovery and estimation cannot produce promotable packages |
| An error report is not a release decision | Documents describe tolerated errors; code contains successful exits and disabled range stops | Structured results and scoped exception decisions; required checks cannot silently be skipped |
| Code and retained data have different lifecycles | Copy-forward instructions in every source; actual NCIt script differences; MTH old/prev links | Code ships from Git; release dependencies are immutable data bundles |
| Reproduction requires more than `.src` output | NCIt prior `tmp`; MTH external Meta/subset links; SNOMED target NCImeta inventory | Archive the complete declared dependency closure and prove restoration |

The insertion contract and agreed source representation rules determine correctness. Current code is evidence of behavior and a valuable comparison oracle, but known defects should not become requirements merely to obtain byte-for-byte equivalence. Historical prose remains useful context; obsolete operational paths should be labeled and removed from the active runbook.

## Required baseline and retention model

### Replace the single “previous” parameter

| Dependency role | Meaning | Required treatment |
|---|---|---|
| `replacement_baseline` | Source version actually being replaced in NCImeta | Explicit per source; verify against the target database before insertion |
| `comparison_baseline` | Prior release used for QA/change detection | Independently selected; identify exact raw/derived comparison artifacts |
| `publisher_history` | Publisher releases needed to interpret changes/history | Include intervening releases when the transformation requires them |
| `reference_ncimeta` | Target inventory, source metadata, precedence, and any other NCImeta state used during preparation | Pin a named release/export and its hashes |
| `identity_state` | Prior AUI/CUI/SAID maps or other persistent mapping state | Version and retain explicitly; do not reconstruct from whatever folder is present |
| `engine_and_policy` | Code, mappings, defaults, normalization, and source-specific representation rules | Immutable Git commit/package identity independent of all data baselines |

For NCIt August → October, `replacement_baseline` is August. `comparison_baseline` may also be August, or September if September's data is useful and available. Copying code from a September working directory creates neither a replacement dependency nor a requirement to insert September. If a source genuinely requires intervening publisher history, declare and restore that history separately.

Distinguish real historical inputs from parameters that exist only to edit copied files. For example, the prototype's `prior_previous_version` helps replace old version strings in inherited metadata; that alone does not make a second prior release's data intrinsically necessary. Regenerating metadata from explicit relationships removes this accidental dependency.

MTH requires more care when an intervening UMLS release was not inserted. Build the transition from the actual installed source/CUI/AUI state to the current package, including the history interval needed for moved atoms, merges, splits, and bequeathal links. Merely repointing `old` or substituting one `prevrel` value is not an adequate migration rule; test the composed identity transitions against the selected installed baseline.

If October was deliberately prepared to follow a still-pending September insertion, declare that dependency and keep it waiting until the dependency is satisfied. If September is skipped, rebase the affected metadata and source-dependent state to August, rerun dependent validation, and produce a new candidate identity. Do not silently relabel an already validated package.

`sources.src` low-source and `termgroups.src` low-termgroup values also express ordering/precedence relationships, especially for new sources. They should be generated and validated against explicit metadata rules; they are not universally “the same RSAB with an earlier date.”

### Retain by dependency, not by folder count

Both `MTH_2026AA/old` and `prev` pointed to `MTH_2025AB`, which was not staged locally at inspection time. Older and sizeable releases are intentionally retained in S3 for several years. The links therefore identify inputs to retrieve when needed, not a finding that the baseline has been lost. The scripts need files behind those links, including `ncisources.spec`, `Meta/MRSAB.RRF`, and `src/cui_said_map`. A planned run should resolve and stage those declared dependencies automatically before starting any transformation. [E2](evidence.md#e2-prior-data-and-archive-closure)

There are two different archive implementations. Shared `Archives.pm` excludes `tmp` and can remove files outside its whitelist. The deployed `push_s3.csh` instead tars the whole source directory, so it normally includes `tmp`; these must not be conflated. However, its tar operation preserves symlinks rather than including their external targets. MTH's inversion archive therefore does not by itself contain the UMLS package/subset data linked from elsewhere. MTH instructions separately upload the UMLS tree, but no inspected manifest ties those artifacts into a verified restorable unit.

Keep the existing separation between S3 history and a small server working set. Make local cleanup depend on verified archival coverage and the needs of active runs, rather than interpreting a folder-count rule as the dependency model. Before local eviction, establish that source code, native packages, derived inputs, maps, comparison evidence, and metadata snapshots can be restored. Store immutable run packages; append insertion logs/receipts as separate artifacts instead of overwriting the only archival object with `--update`.

The transfer operations already exist. Reuse `/local/content/MEME/MEME5/ncim/bin/list_s3.csh`, `pull_s3.csh`, and `push_s3.csh`, including `push_s3.csh inv <VSAB> --update` where the current archival workflow requires it. `pull_s3.csh` supports inversion archives in both `.tgz` and `.tar.gz` forms and separate `ncim` and `umls` trees. This migration does not require building a replacement S3 client. [E14](evidence.md#e14-existing-s3-tools-and-the-integration-boundary)

Implement the artifact resolver as a thin lifecycle adapter over those operations. Its responsibilities are selecting the explicitly declared baseline, reusing a verified local copy, invoking the appropriate existing pull operation when needed, restoring companion dependencies, and verifying the required files before marking the run ready to build. Record object identity/version metadata where available and a manifest checksum; bucket versioning was not inspected. For example, restoring an MTH inversion may require both `pull_s3.csh inv <MTH_VSAB>` and `pull_s3.csh umls <UMLS_RELEASE>` to resolve its external Meta links. Selecting the correct NCImeta reference release is a separate dependency decision.

Apply targeted hardening to the shared scripts where the new execution contract requires it: propagate transfer/extraction failures, validate completeness before reuse, and avoid concurrent writes to the same destination or shared temporary file. The current pull tool has fixed server destinations and rejects existing target directories; it does not already provide arbitrary isolated staging. Initially serialize operations for each destination. A partially restored directory needs diagnosis rather than automatic deletion or acceptance. Optional destination/receipt options can be added to the existing tools if needed.

One restore behavior needs an explicit runtime contract: the UMLS pull removes `DVDIMAGE/jre`, while MTH's `runmmsys.s` references Java beneath that directory. A restored replay must resolve its compatible Java runtime before MetamorphoSys starts. This was identified by code inspection; no failed restore or inversion was observed.

Keep the current whole-release restore path initially. Smaller dependency bundles and selective extraction are later optimizations only if measured transfer/storage costs justify them; compressed archives may require downloading the whole object. Evict cached data after use according to active-run pins. A baseline that is archived and retrievable is available, even when its server directory is absent; fail preflight only if required retrieval or verification cannot succeed.

## Target architecture and operator workflow

Use a small, explicit pipeline graph. A Python CLI is a reasonable control-plane implementation, while existing Perl and tcsh transformations remain isolated subprocesses during migration. A large workflow platform is unnecessary unless operational requirements establish a need for one.

```mermaid
flowchart LR
    A[Acquire and identify inputs] --> B[Resolve baselines and discover changes]
    B --> C[Review metadata and source policies]
    C --> D[Estimate atoms and reserve IDs]
    D --> E[Build candidate]
    E --> F[Validate and reconcile]
    F --> G[Test insertion and required follow-up]
    G --> H[Validate final package]
    H --> I[Ready for insertion]
    I --> J[Record insertion and archive dependencies]
```

Each stage declares its inputs, outputs, interpreter/runtime, validation, and restart behavior. Its identity depends on the relevant input hashes, code/policy versions, environment, and baseline identities. A changed upstream artifact invalidates dependent stages. A completed process, an existing file, or a sentinel is insufficient evidence that a stage can be reused.

Proposed operator commands could be `plan`, `discover`, `build`, `validate`, `compare`, `status`, and `package`. The plan should explain every selected baseline and outstanding decision before a long run starts. The command names are illustrative; the important contract is that both interactive and unattended use have identical semantics and structured results.

A release manifest should include source/VSAB, native package identities, comparison and replacement baselines, NCImeta reference snapshot, source disposition plan, code/policy revisions, ID reservation bounds and receipt, expected outputs, stage results, exceptions, and final output checksums. Secrets stay in the execution environment rather than the manifest.

Treat code, native data, dependencies, run evidence, and final output as distinct lifecycle roles. Initial dev setup preserves the production physical paths; these roles do not imply new top-level directories:

| Role | Initial placement and contract |
|---|---|
| Code and policy | Version in Git and deploy at the existing shared/source-specific locations; stop manual copy-forward through the planned code migration |
| Native data | Preserve the source's existing `orig` and publisher `mr` locations; record identities and keep original bytes |
| Prior/reference dependencies | Resolve the declared source/version folders, maps, and named NCImeta/UMLS releases at their standard paths |
| Run evidence | Associate configuration, locks, logs, and receipts with the exact run; explicitly select any new test-artifact locations |
| Final output | Retain existing paths; identify each file's actual workflow stage and freeze the validated package identity |

A physical relocation needs a deliberate design decision with its reason and migration impact. The dev and production release-folder sets need not match. Only the current run's declared dependencies determine which folders must be available.

During compatibility migration, retain the existing `bin/etc/orig/src/tmp` layout at the standard development paths. As the code migration proceeds, `bin` must resolve to the selected pinned code package rather than inherited executable state from another release or a moving shared library. Start with one legacy inversion at a time in its selected release folder and a separate process: the shared library uses process-wide state, fixed temporary filenames, relative paths, and mutable record templates. Source-folder inventories need not match between servers.

Move source-family definitions, VSAB mappings, RELA/inverse mappings, ATN/TTY definitions, normalization rules, known source exclusions, and release-scoped decisions into reviewed configuration. Generate `sources.src`, `termgroups.src`, TREF metadata, and MRDOC from those same inputs. An operator decision becomes a policy/manifest change followed by regeneration, not an undocumented edit of generated output.

Preserve the exact insertion dialect while doing this. The writers, field-description files, MTH intermediate rows, and historical QA have drifted; do not declare a generic schema authoritative without checking the actual loader contract. Preserve typed identifiers and their qualifiers, `CUI_CURRENT` versus `CUI_PREVIOUS`, relationship direction/grouping, suppression/release flags, context encoding, trailing delimiters, normalization, and the attribute MD5 field. Use SHA-256 for provenance independently; changing a format-required MD5 value is a semantic change.

## Phased migration, ordered by risk prevention

### Priority 1: establish isolated replay/comparison and trustworthy validation

**Timing: immediate, together with priority 2. Owners: platform maintainer and QA lead.**

Build a small test apparatus on a dedicated Linux development worker, with independent storage and runtime configuration. Accept a source/version plus candidate code revision, resolve a reviewed historical case, retrieve/freeze the official inversion and required inputs using the existing S3 tooling, execute candidate code privately, and produce independent validation and comparison reports. Do not use meme-edit's working directories, production mutation APIs, production ID allocator, or official archive update path. A separate importer test database can be added after file-level replay is established; existing meme-test/release administration scripts are not ordinary replay steps.

Compare equivalent workflow stages using an explicit per-output reference map. A directory name is insufficient: SNOMED insertion appends semantic types to `src/attributes.src`, while archived `src/attributes.orig` preserves its inversion result. Retain existing operational paths and freeze file hashes before later enrichment or corrections; record each stage's inputs and outputs so a saved `.orig` filename is a compatibility detail rather than the sole provenance record. Pin historical NCImeta metadata and prior-state inputs instead of consulting today's `latest` data. Compare exact bytes where possible, then full-record multisets and semantic relationships with consistent generated-ID correspondence. Preserve duplicates, group structure, endpoint direction and meaningful metadata. Source-specific equivalence allowances need evidence and negative fixtures; the SNOMED baseline profile retains every generated ID. See [the detailed test architecture](test-architecture.md).

Introduce independent preflight and output checks around the current engines. Required native files or baseline state that cannot be resolved, invalid ID reservations, unresolved `XX-`/`###` values, unknown representation decisions, failed subprocesses, and incomplete expected outputs must produce structured failures. An archived input awaiting restoration is a preparation step rather than a missing-data defect. Existing pull tools can prepare inputs while the common lifecycle is being built. Disable interactive “continue anyway” paths for mandatory conditions.

Characterize and correct the confirmed field-monitor defect and MTH source-plan preflight error with focused regression fixtures. Validate both SAID bounds independently of the legacy QA entry point. Make readiness depend on required validation results and adjudicated findings, never just the shell exit code. [E8](evidence.md#e8-qa-success-is-not-reliable-evidence-of-valid-output) [E9](evidence.md#e9-focused-local-checks)

**Exit criteria:** a simple request produces a reproducible report on the development worker; an unchanged-engine historical replay matches its frozen official reference under the declared profile; comparator fixtures detect deliberately introduced defects; production staff work is unaffected; intentional negative cases cannot produce a ready package; missing historical inputs cannot be replaced by empty baselines; interrupted builds cannot leave a package that appears complete; QA findings remain attached to the exact output hashes they evaluated.

### Priority 2: version operational code and remove copy-forward code state

**Timing: immediate, together with priority 1. Owners: inversion lead and adapter maintainers.**

Inventory deployed source-specific scripts, specifications, mappings, shared defaults, and interpreter requirements for all three workflows. Import operational code into Git with provenance to its source folder, then review differences before choosing canonical versions. Do not bulk-select the newest copy: October NCIt's changes include release data that should become configuration. Retain the original release code in historical archives for reproduction while future runs select pinned code packages.

Use the verified meme-edit production snapshot as this import's source, following the [implementation starting-point decision](#implementation-starting-point-operational-code-on-meme-edit). Establish a clean implementation branch from it; earlier project rework branches do not supply the foundation.

The [baselining procedure](baselining.md) specifies the first steps: identify active code, capture it read-only with provenance, compare it with Git, import through a separate checkout and branch, verify/tag the snapshot, and establish unchanged-engine replay before modernization changes are evaluated.

Give every run an explicit engine revision and source-policy/configuration identity. Stop obtaining executable code by copying the prior release's `bin`, and remove recurring edits to dates, paths, and routine comment state. This does not require replacing the Perl transformations. Keep licensed/native datasets in the existing archive/storage system. Where shared S3 scripts already have a repository owner, reference that version rather than fork them into the inverter; otherwise bring them under version control in the repository that owns NCImeta operations.

Adopt the [common configuration schema](configuration.schema.json) while doing that inventory. Map every consumed legacy parameter to a canonical field, a derived value, or an obsolete copy/edit mechanism. Adapters must preserve semantic differences such as RF2 view versus publisher release, and MTH's two reserved SRC atom IDs. The short test request resolves into this same configuration rather than introducing separate source-specific vocabularies. [E16](evidence.md#e16-common-configuration-and-legacy-name-mapping)

**Exit criteria:** a current release can select reviewed code without copying an older release's executable files; deployed versions are identifiable; routine release changes have a defined configuration location; improvements and rollback are reviewable in Git.

### Priority 3: make baselines and the common lifecycle explicit

**Timing: high, following the initial validation/code baseline. Owners: platform maintainer, release owner, and one operator per source.**

Define replacement baseline, comparison baseline, publisher history, identity state, and reference NCImeta snapshot independently. Make NCIt August → October a normal plan, whether September is absent or useful only for comparison. Distinguish that intentional skip from a genuine pending sequential insertion. Preserve MTH's last-inserted state and any publisher history needed to reconcile it with the current release.

Extend the test apparatus's runner and locked-case contract into the common manifest-driven lifecycle, with the thin dependency adapter over existing S3 scripts, clean work directories, stage receipts, dependency-based restart logic, and package promotion mechanism. Avoid a separate incompatible runner/manifest for production migration. Snapshot NCImeta metadata once per run rather than making repeated calls to `latest` during transformation and QA. Separate discovery/estimation from the final build and pin the ID reservation for a candidate.

Use existing list/pull/push/update operations to prepare selected dependencies and publish the normal archives. Verify a representative historical restore, including external links and the MTH Java runtime, as an integration test. Limit shared-script changes to demonstrated failure handling, provenance, destination, or concurrency requirements. A new archive service, wholesale S3 rewrite, and smaller baseline bundles are not prerequisites. Classify each active release as exploratory, preparing, candidate, waiting on a declared baseline, ready, inserted, or retired.

Model MTH's preliminary and final ID passes explicitly. Changing the SAID range invalidates all dependent maps, atoms, attributes, relationships, merges, contexts, and QA. Do not resume only half of that graph. Test insertion must identify the final package, and any subsequent STY generation, manual correction, or output change must create a new candidate and invalidate the relevant evidence.

**Exit criteria:** a run explains and resolves every required historical input using the existing storage system; a clean rerun with the same manifest is reproducible; two isolated runs cannot share scratch files; a skipped NCIt month requires manifest choices rather than script edits; local cache eviction does not invalidate an active run.

This phase is a process overhaul even while calling Perl: it changes what a release is, how dependencies are resolved, what success means, and how state is retained. It should not reproduce the prototype's copy-and-edit workflow behind a new command name.

### Priority 4: consolidate metadata and representation contracts

**Timing: high; source-rule review can start alongside priorities 1–3. Owners: source domain reviewers and QA lead.**

Create one versioned representation specification per source and one authoritative operational runbook generated from the pipeline contract. Resolve the documented conflicts in the evidence notes, especially SNOMED association eligibility/inverses and MTH old/prev semantics. Migrate conservation review into machine-generated accounting plus scoped human decisions.

At each transformation, account for input records by accepted, transformed, intentionally excluded, deduplicated, and rejected categories. Include explicit expansion factors where one input creates multiple output records. Aggregate by source, term type, attribute, relation, group, and exclusion reason. Record representative source identities for each category so counts can be traced back to input. Counts alone cannot prove semantic correctness.

Legacy “expected error” lists should become source/rule/finding-specific decisions with rationale, reviewer, version scope, and review conditions. Correct outdated rules when data is valid; do not retain millions of irrelevant legacy errors as an implicit universal waiver. In particular, AA/AB MTH output counts are affected by which sources are updated; compare the selected source plan and reconciliation state, not just total row counts.

**Exit criteria:** all metadata can be regenerated; inverse definitions are reciprocal and agree across RELMAP/MRDOC; every observed omission has a policy or an explicit failure; database-dependent QA uses an identified snapshot; final readiness has no unclassified mandatory findings.

### Priority 5: replace transformations incrementally

**Timing: after the preceding acceptance gates. Owners: adapter maintainers and domain reviewers.**

NCIt is the recommended first semantic migration because two adjacent working releases and a relatively bounded conversion chain are available. First remove hardcoded dates/paths and one-off subsource logic. Then replace TREF preparation and record emission in small units, preserving role-group membership, qualifier interpretation, direction, source mappings, and normalization. Keep intermediate comparison formats until equivalent native-to-output accounting replaces their QA purpose.

SNOMED follows, with stable SCTID-keyed representation mappings, explicit US language preference, active/inactive policies, concrete values, association eligibility, ICD map-target inventory, and module dependencies. Keep Snapshot as the supported input mode until Full-to-Snapshot reduction is explicitly implemented and tested. A `Release=Full` configuration toggle alone is insufficient evidence of correct handling of historical versions. Official RF2 release views and module dependencies reinforce the need to pin the input view and compatible modules. [SNOMED release views](https://docs.snomed.org/snomed-ct-practical-guides/snomed-ct-terminology-services-guide/5-service-implementation-considerations/5.3-release-types-and-versioned-views), [module dependencies](https://docs.snomed.org/snomed-ct-specifications/snomed-ct-release-file-specification/reference-set-release-file-specification/5.2-reference-set-types/5.2.4-metadata-reference-sets/5.2.4.2-module-dependency-reference-set).

MTH's semantic rewrite should come last because it reconciles publisher history with existing NCImeta identity and source state. Its validation, code control, and baseline-selection improvements belong in priorities 1–3. Keep MetamorphoSys and the declarative specs behind pinned interfaces until the source-plan, AUI movement, CUI merges/splits, skipped-release history, bequeathal directions, and context generation are covered. Evaluate MetamorphoSys replacement as its own decision rather than changing subsetting, identifier handling, and serializers together.

**Exit criteria for each replacement:** reviewed equivalence against restored historical transitions, targeted negative and boundary cases, a live shadow run, importer acceptance, and an explained decision for every remaining difference. Semantic comparison must remap identifiers consistently across all files; it must not ignore IDs or drop duplicate records to make results look equal.

### Priority 6: add optional assistance and simplify the operator experience

**Timing: after lifecycle stability; read-only guidance and documentation improvements can start earlier.**

Provide a concise CLI or small UI showing selected baselines, required decisions, progress, validation failures, and the exact package ready for insertion. Add the optional skill over that interface. Retire executable copies in release folders, manual code toggles, and superseded runbooks only after successful restore/shadow/cutover gates. Keep an explicit compatibility route until each source has passed its own gates.

**Exit criteria:** the source can be operated without tribal knowledge of release folders, required checks are equally enforced with or without AI, and rollback to a previously approved code/artifact combination is documented. Reverting inverter code does not reverse an insertion; database rollback remains a separately tested insertion-team procedure.

## Validation scenarios that must drive the migration

1. **NCIt August → October:** September absent, available only for comparison, and prepared-but-never-inserted variants. Validate low-source/low-termgroup relationships against the selected replacement plan. No implicit September requirement.
2. **NCIt source evolution:** a new subsource such as BLOODPAC, new ATN/TTY/RELA, role groups spanning reordered input, singleton groups, unknown Maps_To values, duplicate provider records, and intentional self-relation exclusions.
3. **SNOMED representation:** active/inactive endpoint combinations for each association type; reciprocal RELA definitions; US/GB term preference; concrete values; maps to absent target codes; module compatibility; and filtered description attributes.
4. **MTH state transitions:** all disposition values, an updated source with unchanged peers, moved AUIs in a kept source, CUI merges/splits, bequeathal links, missing prior maps, and an intervening UMLS release that was not inserted.
5. **Serialization and identity:** exact field counts/dialect, empty terminal fields, reserved delimiters, Unicode transformations, attribute digest behavior, qualified cross-source references, range exhaustion, and consistent identifier remapping across dependent files.
6. **Operational failure:** missing native or reference files, a stale metadata snapshot, interruption after a partial file write, failed command in a pipeline, changed policy after a checkpoint, concurrent runs, insufficient disk, and final-file mutation after QA.
7. **Archive reproduction:** restore with the original working directories unavailable and prove that external symlink targets, native packages, historical state, code, and validation configuration are all resolved from the manifest.

Use exact comparison when output is intended to remain identical. Where old output order or generated IDs are unstable, use a documented semantic comparison that preserves multiplicity, identifier types, qualifiers, graph direction, and grouping. Validate intentional corrections independently of the old implementation so that a known old defect is not reproduced merely to pass a comparison.

## Skill versus scripts

| Concern | Deterministic pipeline | Optional skill |
|---|---|---|
| Transform source records and allocate/use IDs | Owns execution and invariants | Invokes the supported command |
| Determine whether a package is eligible | Enforces mandatory checks and exact artifact identity | Explains the result; cannot override it |
| New metadata or unfamiliar source change | Produces a structured difference and blocks unresolved rules | Helps inspect examples and draft a policy change |
| Troubleshooting | Provides stage inputs, logs, diagnostics, and supported restart points | Connects evidence, suggests hypotheses, explains remediation |
| Reproducibility and unattended operation | Runs without any model | Optional, with its version/model/trace recorded when used |

A skill can reduce training time and make this environment much easier to investigate. It can also introduce variable command selection, incomplete procedures, unsupported fixes, and inconsistent interpretation of documentation. Those risks are especially relevant here because the current instructions already contain contradictions and broad error waivers.

The appropriate boundary is an assistant that proposes changes to reviewed policy/configuration and then invokes the deterministic pipeline. It should not invent mappings, mutate raw inputs, directly patch final `.src` files, select a missing baseline by guess, suppress required QA, or independently declare a release correct. Approval and release checks must be enforced by the underlying system, not just written in `SKILL.md`.

OpenAI's skill guidance supports packaging deterministic work as scripts and testing skills with captured runs and explicit checks. Use those facilities to evaluate operator guidance, not as proof of transformed-data correctness. Test the skill on missing baselines, new metadata, misleading historical instructions, failed QA, and attempted bypasses. The same pipeline must succeed or fail identically when invoked directly. [Skill construction](https://developers.openai.com/plugins/build/skills), [skill evaluations](https://developers.openai.com/blog/eval-skills).

Treat the requested 100% reliability as a release acceptance requirement: deterministic transformations, complete declared inputs, validated semantics, classified exceptions, and evidence tied to the exact inserted package. Neither an LLM's confidence nor a successful historical comparison alone establishes that requirement.

## Recommended first backlog

1. Establish the isolated development worker and request/replay/comparison apparatus; define acceptance checks, fix confirmed validation defects with focused regressions, and tie QA results to final artifact hashes.
2. Version the apparatus, canonical source-specific code and configuration, eliminating future copy-forward executable state.
3. Specify baseline roles and the skipped-month transition; pilot the common lifecycle using the existing S3 tools, with a representative restore integration check.
4. Consolidate source metadata and adjudicate documented representation conflicts.
5. Replace NCIt components, then SNOMED components, then MTH reconciliation components behind the acceptance gates.
6. Add a skill as an optional operator interface and retire superseded recipes after source-specific cutover.

The immediate reviewable deliverables should therefore be the test-worker/replay/comparison design and request contract, a validation acceptance specification, canonical versioned operational code, and a baseline/lifecycle specification demonstrated by a single-source pilot away from meme-edit. Existing S3 history and transfer tooling are foundations to reuse. Expanding the existing inversion shell wrappers without the code, state, and acceptance contracts would retain the underlying lifecycle problems.
