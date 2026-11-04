# Evidence notes and documentation reconciliation

Read with [the assessment](assessment.md) and [the machine-readable evidence manifest](evidence-manifest.json). Server paths below are relative to `/local/content/MEME/MEME5/inv` unless explicitly qualified. Code line numbers refer to the November 3, 2026 snapshot. Document section names identify content; no rendered Word page numbers are asserted.

## Source documents

- D1: [Basic inversion instructions.docx](</Users/shapirod2/Downloads/Basic inversion instructions.docx>). Relevant sections: Preparation; initial versus real inversion; QA; Post-inversion.
- D2: [MTH Inversion.docx](</Users/shapirod2/Downloads/MTH Inversion.docx>). Relevant sections: directory setup and old/prev; source mapping; four inversion scripts; skipped previous insertion; QA and cleanup.
- D3: [SNOMEDCT_US inversion for NCI.docx](</Users/shapirod2/Downloads/SNOMEDCT_US inversion for NCI.docx>). Relevant sections: NLM-independent inversion; Edit MRDOC; historical NLM `.src` approach; Notes on representation changes.
- D4: [WCI Documentation - SNOMEDCT_US inversion for NCI.docx](</Users/shapirod2/Downloads/WCI Documentation - SNOMEDCT_US inversion for NCI.docx>). Expanded procedure sharing substantial content with D3; includes corrections and retained earlier examples.
- D5: [NCIt Inversion Documentation.docx](</Users/shapirod2/Downloads/NCIt Inversion Documentation.docx>). Relevant steps: copying prior files; source/termgroup metadata; role groups; TREF; TDE QA; subsource routine; conservation; archive/retention.

All five were extracted in full using macOS text conversion. Package inspection found no media parts, footnote/endnote/comment parts, tables, or tracked insertion/deletion elements in the inspected documents. No DOCX was edited or re-exported. The exports supplied by the user were reviewed; access to the rest of the Drive folder was not established. Credentials present in source documentation are intentionally not reproduced here.

## E1. Previous is not one relationship

**Confirmed:** D3/D4 explicitly define the previous SNOMED source as the version last inserted into NCI Meta, which may differ from UMLS. The deployed `sources/SNOMEDCT_US_2026_09_01/etc/README.txt`, introductory steps, makes the same distinction.

**Confirmed:** `sources/MTH_2026AA/initdir.s:7–25` separates the release used for `prev` from the last actually inserted release used for `old`:

```text
set prevrel=2025AB
ln -s ../MTH_$prevrel prev
# [make link from "old" to the last MTH_20xxAX dir that was actually inserted]
```

D2's directory instructions instead suggest old and prev may be the same. Later D2 and `invert1.s:6–9` explicitly require special handling when a previous UMLS release was not inserted. The source script distinction is therefore supported by multiple parts of the workflow, rather than being a naming preference.

**Confirmed from the saved QA explanation, not a fresh database query:** `sources/NCI_2026_10D/etc/qa/conservation.txt:58–67` reports expected low sources ending in `2026_09D`, database low sources ending in `2026_08E`, and explains that September had not yet been inserted.

**User clarification:** NCIt may intentionally skip a month, with August the prior version and October the current version. September must not be inferred as a mandatory insertion dependency.

**Recommendation:** distinguish replacement baseline, comparison baseline, publisher history, reference NCImeta snapshot, and code provenance. Represent an intentional skip and a genuinely pending sequential insertion as different plans.

## E2. Prior data and archive closure

**User clarification:** older and sizeable release folders are intentionally archived in S3, with history going back several years. Local absence is expected. The filesystem observations below establish which inputs were not staged locally; they do not establish missing archival data or a failure of the archival process.

**Confirmed live dependency checks (local filesystem only):**

| Path | Observation |
|---|---|
| `sources/MTH_2026AA/old` | Symlink to `../MTH_2025AB`; target not staged locally |
| `sources/MTH_2026AA/prev` | Symlink to `../MTH_2025AB`; target not staged locally |
| `old/ncisources.spec` | Not accessible locally until the dependency is restored |
| `old/src/cui_said_map` | Not accessible locally until the dependency is restored |
| `old/Meta/MRSAB.RRF` | Not accessible locally until the linked dependencies are restored |
| `sources/NCI_2026_09D/tmp/nci_roles3.tmp` | Present |
| `sources/NCI_2026_08E` | Not present locally |
| `sources/SNOMEDCT_US_2026_03_01` | Not present locally |

The absence of the old SNOMED folder is not by itself a missing native-input dependency in the current RF2 parser. It matters for restoration, code provenance, metadata comparison, and any explicitly selected prior-release checks. Dependencies must be derived from the actual workflow, not from every old-looking configuration key.

`archive/projects/TDE_QA/checkall-qual.csh:40–62,389–412` declares current/previous release paths and reads the previous release's `tmp/nci_roles3.tmp`. It also uses previous TDE comparison products and prior `orig` files.

`INV/lib/Archives.pm:40–50,543–557` defines an archive whitelist that omits `tmp` and removes entries outside it. By contrast, the deployed external `/local/content/MEME/MEME5/ncim/bin/push_s3.csh:70–79` uses:

```text
tar -zcvf $SOURCE_NAME.tgz $SOURCE_NAME
aws s3 cp .../inv/sources/$SOURCE_NAME.tgz
```

That tar includes `tmp` inside the release directory, but follows neither MTH's external `Meta`/`METASUBSET3` targets nor the previous release behind old/prev. Its `--update` mode can replace the prior object. No S3 object/version history or restore was inspected, so archival data loss is not asserted.

D5 says to keep the two most current NCIt versions and delete older ones. The deployed NCIt README instead describes archiving the previous inversion after insertion is complete and the next month's data arrives. D2 and `invert2.s:39–57` separately archive inversion/UMLS data and then describe deleting the prior inversion and UMLS trees.

**Recommendation:** use the existing S3 history as the archive tier, automatically resolve/stage the transitive dependencies selected for a run, and verify restoration before local eviction. Retaining all old folders on the server is unnecessary. Exact S3 keys, object versions, and restore completeness remain unverified in this assessment. Do not apply shared `Archives.pm` behavior to `push_s3.csh` by assumption.

A subsequent inspection confirmed existing list, pull, push, and inversion-update operations in `ncim/bin`; see [E14](#e14-existing-s3-tools-and-the-integration-boundary). The lifecycle should reuse those operations. The remaining concern is explicit dependency selection and verified preparation, rather than absence of transfer tooling.

## E3. NCIt code is a carrier of release state

D1 and D5 direct the operator to copy scripts and edit them for the new release. D5 step 15 requires toggling `processSubsourceAtoms`, entering new source information, and disabling the routine after use.

The actual September-to-October 2026 `bin/invert_NCI.pl` diff enables the routine and changes hardcoded source metadata from FDA-NIH-MoRE to BLOODPAC. This is direct evidence of the requested copy-forward problem. It is not merely a hypothetical maintenance concern.

Additional release-specific executable edits are present in:

- `sources/NCI_2026_10D/bin/create_tref.pl:6,20,35,131,173`: native filenames contain `20261026`.
- `bin/compare_exportrels2tref.s:10–14`: absolute paths contain `NCI_2026_10D`.
- `bin/create_rolegroups.pl`: a release-specific input filename.
- `archive/projects/TDE_QA/checkall-qual.csh`: release settings and shared scratch filenames.

`tref_2_relational_files.pl` is a tcsh script despite its `.pl` suffix. An execution registry must respect the actual interpreter contract rather than infer it from filenames.

`create_tref.pl:113–115` reports an unrecognized Maps_To relationship as text, without an accompanying nonzero failure at that point. The affected input can therefore fall outside known mapping output paths. Native-data discovery and rejection accounting should catch such cases before a package is eligible.

## E4. SNOMED discovery and manual metadata

`sources/SNOMEDCT_US_2026_09_01/bin/invert_rf2.pl:979–994` emits an `XX-<typeId>` relationship label when no representation mapping is found. D3/D4 instruct operators to find these values after the first run and then modify `SCT.RELMAP`.

`bin/invert.s:43–51` deletes/rebuilds MRDOC and fills some placeholders mechanically. D3/D4 then instruct operators to edit MRDOC and comment out regeneration before another run. The WCI version additionally warns to retain `cd ../src` while commenting out the remaining block. This turns the mutable script into both a transformation and a restart-state record.

`etc/sct.cfg:8–24,35–56` selects the US September 2026 Snapshot, identifies the native files/refsets, and records SAID bounds. `bin/invert.s:28–34` reads ICD/ICD10CM target inventories from the NCImeta `202608/META/MRCONSO.RRF`. The referenced file was confirmed present.

**Recommendation:** separate discovery from final generation, key representation decisions by stable source identifiers, generate MRDOC from reviewed mappings, and pin the NCImeta target inventory.

## E5. SNOMED policy conflicts

### Inverse names

D3's relationship-map example uses `procedure_approach_for` while part of its MRDOC example uses `procedure_approach_of`. D4 includes an `_of` correction and retains an earlier `_for` suggestion labeled potentially incorrect. The deployed `etc/sct.cfg:521–522` uses:

```text
has_procedure_approach|procedure_approach_of|RT
```

**Recommendation:** maintain one mapping definition and validate inverse reciprocity plus agreement among RELMAP, emitted relationships, and MRDOC. Existence of an inverse row alone is not sufficient.

### Historical associations and inactive endpoints

D3/D4's representation notes expect some `refers_to` associations to involve obsolete descriptions and describe dropping certain associations involving current descriptions. The deployed `invert_rf2.pl:1033–1078` requires the association row and both endpoints to be active. `get_description_status:1530–1545` sets description activity from description/concept status; `process_descrs:853–868` excludes inactive descriptions and reinforces active state for emitted descriptions.

This demonstrates a policy/implementation conflict requiring domain review. It does not establish which policy should replace the other, or quantify affected production records without a native-data analysis.

### Native input view

The deployed configuration offers Snapshot and a commented Full option. The inspected processing loops iterate rows rather than declaring a separate historical-version reduction stage. Full support should be characterized before being enabled. Publisher specifications distinguish Full historical rows from Snapshot state; these views are not interchangeable inputs.

### Superseded workflow

D3/D4 retain the former NLM `.src` acquisition path and its NLM-SAID-range reservation instructions alongside direct-RF2 instructions. The documents' introductory independent-inversion test status is historical relative to the current server artifacts. Keep these modes explicitly separate; the old range convention must not be carried into a direct-RF2 release by accident.

## E6. MTH is a stateful source plan

Primary locators:

- `sources/MTH_2026AA/guess.ncisources.spec.pl:5–38`: compares `old/ncisources.spec` with current MRSAB and proposes dispositions.
- `preinvert2.s:26–44`: captures NCImeta sources/precedence and runs MetamorphoSys preparation.
- `genmmsysconfigs.pl`: builds the REST subset, excludes direct SNOMEDCT_US, applies termgroup exclusions, selects versioned output, and removes NH attributes.
- `invert1.s:29–30`: compares `old/Meta/MRSAB.RRF` with current MRSAB.
- `invert1.s:54–92`: creates the source update plan and histories for moved AUIs/CUI merges.
- `invert2.s:94–117`: rebuilds atoms and dependent AUI/CUI maps with the final range and runs subsequent specs.
- `invert2.s:100`: reads `../old/src/cui_said_map`.
- `inv2.spec:69–79`: emits moved-atom merges and CUI merge facts.
- `inv3.spec:13–20`: emits bequeathal relationships with current/previous CUI qualifiers.

The generated source plan contains both unchanged and updated sources. Its output size naturally depends on that plan and cannot be interpreted as a complete UMLS replacement dump. D2's observation that AA/AB counts may go down should be explained through source selection and history reconciliation rather than tolerated without accounting.

The source layout is also unusual: root `bin` and `etc` point to `.`, `src/bin` points to `..`, and `src/Meta` points through `Meta3` to an external MetamorphoSys subset. A compatibility wrapper must preserve the working-directory contract until the scripts are parameterized.

## E7. MTH mutates upstream inputs and uses weak checkpoints

`updatevsabs.s:11–34`:

1. Skips work when `DVDIMAGE/vsab.update.is.complete` exists.
2. Extracts MRSAB from the publisher `.nlm` archive.
3. Rewrites its VSABs using `sab.vsab.map`.
4. Copies rewritten MRSAB into Meta/configuration locations.
5. Updates the `.nlm` archive itself.
6. Creates the sentinel.

D2 describes removing the sentinel to rerun, with full directory recreation as a possible recovery. The sentinel contains no declared association with the original publisher checksum, the mapping checksum, or engine version.

`preinvert2.s:48–55` also patches derived subset MRCONSO/MRSAB in place. Those are legitimate transformation stages to model explicitly; they should not obscure the identity of the untouched native package.

**Recommendation:** immutable raw packages, versioned derived views, validated mapping coverage, and restart receipts based on input identities. Retain the exact MetamorphoSys package/JRE/configuration until its replacement is separately validated.

## E8. QA success is not reliable evidence of valid output

`INV/bin/srcQa.pl:52–54,188–202` contains error exits with bare `exit`, which is a successful status absent a separately set failure status. Its SAID min/max discrepancy paths at `215–226` print errors but have the exit statements commented out. The documentation acknowledges this disabled-stop behavior even while other prose says bad ranges prevent QA.

`INV/lib/SrcQa.pm:260–284` can skip a missing MRDOC check and uses a bare exit for placeholder errors. `Logger::logError` records text/counters rather than terminating transformation. Therefore a successful process return cannot serve as package acceptance.

`INV/lib/QaAtoms.pm:69–79` queries current API metadata during module loading, before the CLI has checked its required configuration. `MakeDoc.pm:50–98` makes three live metadata calls. `api_metadata.sh:37,54–62` uses a hardcoded older-host endpoint and `latest` metadata paths. These are hidden environmental inputs to supposedly repeatable processing.

D1/D3/D4/D5 describe tolerated error classes; D2 and `invert2.s:13–38` describe server QA with expected failed steps and large expected counts. Such material establishes the need for classification and domain-aware rules, not permission to ignore whole validation categories indefinitely.

## E9. Focused local checks

These were small, isolated checks of captured/repository code and data, not full inversions.

### Field monitor null handling: reproduced defect

In `INV/lib/FldMon.pm:177–183`, processing a null field increments the `nullable` setting and never increments `ENullFlds`. Reporting subsequently relies on that counter.

```perl
my $m = FldMon->new("");
$m->{nullable} = 0;
$m->process("", 1);
$m->process("", 2);
```

Observed result: `nullable=2; ENullFlds=0; recorded=1`. Two missing required values do not yield the expected null-error count. This finding justifies testing the validators themselves with deliberately invalid fixtures.

### MTH KEEP/UPDATE preflight: reproduced ineffective selection

`sources/MTH_2026AA/preinvert2.s:30` looks for `KEEP`/`UPDATE` in field 2 of `ncisources.spec`; D2 and the deployed specification put the disposition in field 3. On the captured specification, field-2 selection matched **0** rows and field-3 selection matched **46**. The guard cannot validate the intended set using the current field expression.

### Local runtime compatibility: reproduced compile failure

`perl -c INV/lib/SrcDiffs.pm` returned status 255 on the local Perl, reporting `defined(@array)` at line 247. This is a local portability observation; the server's runtime compatibility was not established by this check. Pin the runtime initially and test compatibility before upgrades.

## E10. Environment and schema assumptions need explicit contracts

The checked ENV file assigns `INV_HOME_OLD` to the server's `inv/INV_OLD`, which was empty. Supplemental checks confirmed that its `autoinv.pl`, `SRCbuilder.pl`, and `QA4.pl` do not exist. MTH scripts still invoke these paths; `runQA.s` also sets `INV_HOME` to `/local/content/MEME/INV_OLD`, which was absent. This is evidence that the checked scripts cannot be assumed reproducible from the current filesystem/environment alone. It is not proof of the historical execution environment used when the release was built.

Shared `NLMConfig.pm:23–32` combines configuration through a fixed working-directory file named `temp_con_file`. `NLMInv.pm:30–35` and `IdGen.pm:9–28` maintain singleton/process-wide state. `NLMInv.pm:141–155` derives append-mode next IDs from file tails. `Atom`, `Attribute`, `Relation`, and `Merge` mutate record templates between writes. These properties argue for isolated processes and work directories during migration.

MTH's `inv1.spec` produces extended intermediate atom rows with moved-state/CUI/AUI information; `make.meme4classes.s` strips intermediate fields for final loading. The exact meaning of final CUI-bearing fields must be checked against the loader contract, not inferred solely from an older field-description file.

There is also a schema interpretation concern worth adjudicating: `make.sourcestermgroups.pl:102` names the thirteenth MRREL field `dir` and the fourteenth `mg`, while `inv2.spec:6` declares the thirteenth `RG` and fourteenth `DIR`. That disagreement affects derivation of source relationship-directionality metadata. It is a static inconsistency; its output impact was not measured in this review.

## E11. Prototype findings inform the migration but do not define it

At Git rework commit `d65d9f6`, `run_nci_inversion.sh`:

- Copies previous `bin`, configuration, QA files, and source/termgroup metadata (`326–345`).
- Overwrites selected copied scripts with newer shared copies (`352–361`).
- Edits release values and input filenames in place (`403–594` and later steps).
- Can continue without the previous directory after operator confirmation (`210–221`).
- Treats missing stage scripts/checklists as warnings in several branches.
- Lets an operator continue after new metadata is detected (`782–811`).
- Reports final completion while conservation/proposal review remains manual.

Those behaviors explain why a broader lifecycle is needed. They should not be carried forward simply because the wrapper already implements them.

The prototype README claims offline `api_metadata_export.txt` support. The inspected `INV/lib/MakeDoc.pm` still calls the API directly and contains no reader for that export. `extract_metadata.sh` creates an export, but that does not establish that the consumer uses it. The README's claim that TDE QA is not automated also conflicts with the branch's later integrated checker. This is documentation/code drift within the prototype itself.

## E12. Shared library map and migration boundaries

| Component | Existing responsibility | Migration treatment |
|---|---|---|
| `NLMInv`, `NLMConfig`, `IdGen` | Configuration, process setup, output handles, ID counters | Pin/isolate initially; replace implicit run state with explicit context |
| `Atom`, `Attribute`, `Relation`, `Merge`, `Context` | Record templates and `.src` serialization | Preserve dialect and normalization; migrate with cross-file fixtures |
| `SrcBldr` | Source/root metadata atoms, attributes, merges, relationships | Generate from reviewed source registry and explicit new-source decisions |
| `Hierarchy`, `Contexts` | Parent/child graphs, paths, contexts and attributes | Preserve graph semantics; test cycles, multiple parents, root treatment and scale |
| `MakeDoc`, metadata scripts | Discover and render metadata documentation | Pin reference inputs; generate from one reviewed registry |
| `SrcQa`, `Qa*`, `FldMon`, `LineMon`, `QA4*` | Multiple generations of validation and reporting | Build independent acceptance contracts; migrate useful checks with negative fixtures |
| `SrcDiffs`, `SrcStats`, `SrcReport` | Comparison and reporting | Reuse domain knowledge; verify identity mapping and runtime behavior |
| `Archives`, existing `list_s3`/`pull_s3`/`push_s3` scripts | Listing, restoration, packaging, cleanup, uploads and inversion updates | Reuse existing transfers; add explicit dependency selection, receipts, verification and targeted hardening |
| `autoinv.pl` plus MTH `.spec` files | Declarative scans, joins, filters and record construction | Treat as executable source semantics; keep pinned while characterizing transitions |

`INV/etc/inv_defaults.cfg` is approximately 3,500 lines of paths, templates, and monitoring rules. It is part of the executable specification and must be versioned with the engine. It should not silently change underneath a release when a shared installation is updated.

## E13. Documentation decisions to make explicit

| Conflict or ambiguity | Evidence | Recommended resolution |
|---|---|---|
| Previous means adjacent publisher release, latest inverted release, or last inserted release | D1/D2 versus explicit SNOMED/MTH rules; NCIt lag; user's skipped-month clarification | Named baseline roles, explicit skips, per-source insertion checks |
| old and prev are interchangeable | D2 setup note versus MTH `initdir.s` and skipped-insertion comments | Separate roles even when they resolve to the same release |
| MRDOC is generated output versus manually protected editorial state | D1/D3/D4, current SNOMED wrapper | Version editorial metadata; regenerate output without manual code toggles |
| NCI configuration text is optional versus used to drive QA | D5 historical note versus TDE config extraction and checker | Declare stage-specific required inputs; remove obsolete conversion instructions |
| Fixed example ID count versus estimated/final allocation | D5 900,000 example; D1/SNOMED two-run guidance; MTH two passes | Count/estimate separately, record reservation receipt, validate both bounds |
| Direct RF2 versus filtered NLM `.src` mode | D3/D4 contain both; server uses RF2 workflow | Make direct RF2 the normal route; isolate any retained historical mode |
| MRDOC inverse `_for` versus `_of` | D3/D4 examples and current config | Single domain-reviewed mapping registry and inverse checks |
| Range errors stop QA versus exits disabled | D3/D4 prose and code note; `srcQa.pl` | Mandatory independent range validation |
| All errors must disappear versus broad “ignore” lists | D1–D5 and captured conservation/QA material | Correct invalid rules; scope and review legitimate exceptions |
| Small local working set versus complete historical dependencies | D5 cleanup; MTH deletion; unstaged links; prior QA inputs; user-confirmed multi-year S3 history | Automatic dependency staging from S3, verified restoration, and local cache eviction |
| Source version list alone predicts MTH output counts | D2 count note versus selective source plan and moved-AUI processing | Compare disposition-aware accounting and identity changes |

Resolve these as versioned design decisions with owners and effective versions. The review does not authorize running the destructive, publishing, notification, or administration instructions contained in the source documents; none of those instructions was executed as part of the review.

## E14. Existing S3 tools and the integration boundary

Read-only inspection of `/local/content/MEME/MEME5/ncim/bin` found the following established tools. No S3 transfer, archive update, test-environment provisioning, or index operation was executed.

| Tool | Inspected capability |
|---|---|
| `list_s3.csh:18–46` | Lists indexes, NCImeta releases, UMLS releases, inversion archives, snapshots and temporary storage prefixes |
| `pull_s3.csh:38–104` | Restores `inv`, `ncim` or `umls` to their standard server locations; inversion mode supports `.tgz` then `.tar.gz` fallback and extracts the archive |
| `push_s3.csh:21–27,70–93` | Uploads inversion, NCImeta and UMLS data; `--update` permits replacement of an existing inversion archive |
| `backupIndexes.csh` | Supports a separate index-backup workflow; its archive-related code was read for context |
| `test_insertion.sh` | Documents use of `pull_s3.csh inv ...` when preparing insertion data; also contains separate database/index administration operations, which were not run |

The source archive convention is already defined by these scripts: `inv/sources/<VSAB>.tgz` or legacy `.tar.gz`, with NCImeta and UMLS trees under `mr/ncim/<release>` and `mr/umls/<release>`. These are code-defined conventions; actual S3 contents, versions, and checksums were not queried.

Specific integration constraints from inspection:

- `pull_s3.csh:50–62` rejects an existing destination. Readiness must distinguish a verified existing release from an incomplete previous restore; do not automatically delete or trust a directory simply because it exists.
- `pull_s3.csh:69–80,93–104` does not explicitly gate subsequent actions on each transfer/extraction status. For example, inversion extraction is followed by removal of the downloaded archive, then a final completion message. Stronger completion evidence needs targeted error propagation and output verification.
- `push_s3.csh:71–77` uses the fixed `/tmp/t.txt` name. Shared archive operations should avoid collisions until a task-specific temporary file is introduced.
- `pull_s3.csh:106` removes the restored UMLS `DVDIMAGE/jre`. MTH `runmmsys.s:55,86–92` references Java in that tree. A historical replay needs an explicit compatible runtime installation or configured runtime path after restoration. This is a static contract mismatch to resolve, not a reproduced production failure.
- The current transfer tools use fixed destinations and named archive keys. Arbitrary staging locations, object-version selection, and machine-readable receipts are possible focused enhancements, not existing capabilities to assume.

**Revised recommendation:** keep these scripts as the transfer implementation initially. Add a thin dependency-planning layer that knows which `inv`, `umls`, and `ncim` versions are needed, invokes the existing operations, verifies required artifacts/runtime, records provenance, and hands the prepared inputs to the inversion stages. Replace or extend individual script behavior only where a concrete contract or test requires it.

## E15. Test architecture requirements and design status

The user added explicit requirements for development over the coming months/cycles: candidate inversions should run on a development server or another environment away from meme-edit; a simple source/version request should run updated code; the apparatus should retrieve the corresponding official inversion from S3 and compare outputs.

The proposed [test architecture](test-architecture.md) responds to those requirements. It is a design, not a deployed service. The [example request](request-template.json) contains an unresolved candidate-commit placeholder. No candidate code, archive pull, provisioning operation, production ID reservation, or importer operation was executed for this addition.

Relevant existing observations are the source archives' separate `src`/`insert` stages, mutable archive keys supported by `push_s3.csh --update`, the fixed destinations in `pull_s3.csh`, repeated live metadata calls in legacy QA/documentation generation, the large SNOMED context file, and the limitations of `SrcDiffs.pm`. Those support explicit reference-stage/case locking, private worker paths, historical metadata inputs, bounded-memory comparison, and independent validation of the comparator. They do not establish a particular development host's capacity or availability of every historical metadata snapshot.

## E16. Common configuration and legacy name mapping

The user requested common configuration so equivalent parameters do not have different names across the three sources. The [configuration design](configuration.md), [schema](configuration.schema.json), and three source examples are proposals; they do not implement adapters or change current inversion behavior.

Inspected legacy settings show both naming divergence and meaningful semantic differences:

- NCI `etc/nci.cfg:6–10,147–150,163` uses `VSAB`, `RSAB`, relative directory settings, and `SaidStart`. The inspected file has no `SaidEnd` setting.
- SNOMED `etc/sct.cfg:7–24` uses `RSAB`, `VSAB`, `VSABOLD`, `Release = Snapshot`, native date identifiers, and `SaidStart`/`SaidEnd`. Its `File.INP.*` values name individual native/refset files and separately generated ICD inventories.
- MTH `initdir.s` uses `newrel`/`prevrel`, `invert1.s` uses `rel`/`prevrel`, and `runmmsys.s` uses `release`. These release suffixes describe the publisher version, unlike SNOMED's `Release` input view. MTH's `old` and `prev` have different roles, as documented in E1.
- MTH `range3.spec:1–2` uses `SourceAtomIdBase`/`SourceAtomIdLimit`. `invert1.s:68` and `invert2.s:83` subtract two from the base for SRCbuilder. D2's final-range instructions tell the operator to leave room for two SRC atoms. Thus the canonical complete inclusive range starts two below the MTH atom-specification base; equivalent-looking start fields cannot simply be copied unchanged.
- Shared `NLMInv.pm:67–69` initializes `IdGen` from `SaidStart`; `IdGen.pm:38–40` emits and then increments the atom ID. These consumers, plus source metadata generation, must determine each adapter's exact translation.

The common contract separates `replacement_baseline`, `comparison_baseline`, and `publisher_history`; uses the same `source`, `version`, `engine_ref`, input roles, and full SAID bounds for all three sources; and permits only typed source-specific options. Semantic/provenance checks and legacy-translation replay remain implementation work. Example catalog references and ID ranges are illustrative and do not establish historical input availability or actual allocations.

## E17. User-selected implementation starting point

The user explicitly selected the operational code on meme-edit as the gold standard and requested a fresh effort from that code, rather than continuation of prior project work. This is an implementation constraint, not an inference from the older documents.

The plan now requires a verified, hashed production snapshot and a clean implementation branch based on that snapshot. Prior automation/rework branches remain informative only. The existing assessment snapshot was collected from `ncias-q3793-c`; its exact relationship to the active meme-edit deployment and the currently used source-specific versions must be verified when freezing the implementation baseline. The 39 matching shared modules establish only that comparison's scope, not completeness of repository main as the production baseline.

No production snapshot import, new implementation branch, or replay execution was performed to record this decision. Compatibility is measured against official production behavior and archived results, with intentional defect corrections separately reviewed and validated.

## E18. Development layout and release-folder selection

The user selected `ncias-d3777-c`, confirmed separate storage from production, and directed the initial setup to mirror meme-edit's physical directory layout. Operational code and data should use their existing standard paths. Relocation is a deliberate design change requiring a stated reason and migration impact, rather than a default consequence of building a test apparatus.

The user separately clarified that dev and production can contain different source/version folder inventories. A run uses the releases and dependencies it needs. Extra folders do not block readiness; required absent releases can be restored from S3. No synchronization or cleanup is needed to make the servers' folder lists match, and folder presence does not establish a replacement baseline.

These instructions supersede the proposed separate replay root and default physical-path remapping. The successful namespace probe remains a capability observation, not a selected deployment layout. No alternate replay root or source relocation was created. The [test architecture](test-architecture.md), [configuration design](configuration.md), and [development readiness report](dev-worker-readiness.md) now reflect this distinction.

## E19. Frozen October archive and explicit input/output boundaries

The first actual S3 reference was acquired on dev without extraction: `inv/sources/NCI_2026_10D.tgz`, 546,021,953 compressed bytes, 104 members, SHA-256 `c2332760cc014ddf462b5824b2b1ad720ca844871046753ed14d58fef5526bee`. All 20 archived source-code/configuration entries checked against their captured production hashes match. All five publisher files used by role-group/TREF preparation are present, along with archived TREF intermediates and completed core output. See [the reference boundary record](nci-reference-boundaries.md).

`src/sources.src` has source name `NCI_2026_10D` and low source `NCI_2026_08E`, verified using field 2's meaning in `INV/etc/sources.fields` and the loader comments in `SrcBldr.pm`. This is saved metadata evidence for the August-to-October transition, not a fresh database query. The archived `insert` metadata instead has August source names and July low-source tags. Its exact production role is not yet traced, and it is excluded from the October output reference. Same-named `src`/`insert` files all differ; the atom files have 803,253 versus 798,994 newlines.

The core inverter reads prepared `sources.src`/`termgroups.src` plus current TREF data and writes five core `.src` files. Normal invocation uses overwrite rather than append mode. Role-group/TREF preparation reads the current publisher exports. No previous source folder is opened by those inspected stages; prior-state relationships are supplied in the declared metadata. Metadata acquisition, documentation generation, and QA remain separate coverage/dependency decisions.

The first replay must generate role groups, TREF, and core output afresh. It can use archived source metadata as an explicitly declared fixture, but that does not test how that metadata was acquired or edited. A fully restored completed source folder is not a fresh candidate, and copying official atoms/attributes/relationships/contexts into a candidate cannot establish equivalence.

The dev pull helper was updated from the captured production reference with optional archive retention/download-only behavior and targeted failure checks after 12 network-isolated fixture cases passed. The job selected the existing `meme` AWS profile through the environment. No upload, archive extraction, candidate source-folder creation, or inverter execution was performed in this acquisition/audit step.

## E20. Preparation copies current output; it does not rewrite versions

The user identified the pre-insertion copy step. Inspection found identical `ncim/bin/prep_insertion.csh` files on production and dev. For non-MTH sources, lines 92–93 copy current `src/*.src` and `src/*.RRF` unchanged to `insert` by default or `test` with `-t`; line 104 adjusts group ownership. MTH additionally copies `umlscui.txt` and explicitly includes bequeathal relationships. No filtering or version rewrite is performed. [Preparation review](insertion-preparation-review.md)

This establishes the intended role of `insert`, but does not explain its August-labeled contents in the October archive. Those contents do not correspond to current October `src`. Establish the invocation and subsequent-change history before certifying an archived insertion package; do not infer that prep transformed October into August.

The script does not clear a preexisting non-MTH target or explicitly stop on each copy failure. A clean target inventory, verified copies, and hash-bound staging receipts are therefore necessary modernization gates. These properties alone do not prove the cause of this archive mismatch. No preparation or insertion command was executed for this inspection.

## E21. Fresh NCIt preparation and active core replay

The user selected archived October `src` as the key reference and excluded the archive's `insert` contents/history from this replay. No further insertion-history investigation is required for this case.

`tools/prepare_nci_candidate.py` created the standard dev folder `inv/sources/NCI_2026_10D` from the Git production snapshot plus exactly five publisher inputs and two archived metadata inputs. None of the five generated core files was seeded. All five preparation stages ran offline and exited zero. Regenerated MRCONSO, MRREL, and MRSAT TREF files match the archived SHA-256 values byte-for-byte. The [preparation receipt](nci-2026-10d-candidate-preparation.json) includes inputs, code identities, stage timing, and comparisons.

The official atom file has 803,253 unique contiguous IDs, 781548593–782351845. This is observed historical output evidence for this isolated test, not a production allocation reservation.

At this evidence stage the unchanged core inverter was running offline through `tools/run_nci_core_replay.py`. The first attempt's overly short time limit was corrected after the archived log established a 2,247-second production core duration; that attempt was stopped and preserved before the clean restart with a 7,200-second limit. The [run and restart receipt](nci-2026-10d-core-run-status.json) records that launch. Subsequent comparison and candidate results are recorded below; metadata acquisition, MRDOC generation, legacy API-dependent QA, and insertion remain excluded.

## E22. Completed NCIt src comparison and reproduced term-type defect

The corrected core run exited zero and finished on November 3 at 16:29 PST. Five core row counts match the official October archive. Relationships and merge facts match byte-for-byte; context full-record multisets match including duplicate counts. All attribute content matches after excluding only generated attribute row IDs. All 796,203 non-CONTEXT attributes match including IDs; 469,407 CONTEXT attributes have changed generated-ID assignments. Both attribute ID allocations are unique and span 1–1,265,611. `Hierarchy.pm:785` emits contexts/attributes through unsorted hash-key iteration. No attribute-ID reference types occur in the five selected files.

One atom differs substantively: ID 781756819, AMPHIREGULIN, code 7MGE0HPM2H, CUI C1000. Archived termgroup is `FDA_2026_10D/PT`; fresh termgroup is `FDA_2026_10D/`. All other atom fields/rows match. MRCONSO.TREF line 2 contains FDAPT and an original code and is the first subsource PT input. `invert_NCI.pl:742` omits `tty` where the alternate branch at line 628 sets PT. An offline in-memory probe with the actual installed serializer and combined pinned configuration reproduced the empty/default and retained-template behavior. The historical correction that put PT in the archive is not established.

The candidate's missing FDA termgroup is not in its declared termgroups. SRC/VPT, SRC/VAB, SRC/RPT, SRC/RAB and SRC/SSN, also absent from that per-source fixture, are explicitly accepted by `QaTGs.pm:402-409` and must not be misclassified as new defects. Structural/reference checks passed for both file sets; the independent termgroup check still identifies this candidate defect. Comparison is complete; acceptance FAIL, review required. No candidate output or frozen archive was changed.

Fifteen comparison/corruption fixtures passed locally and on dev. SHA-256 identities of the executed comparison and diagnosis code, exact counts, field examples, file structures, digest checks, typed reference checks, and coverage limits are recorded in the [comparison summary](nci-2026-10d-comparison-summary.json), [full comparison](nci-2026-10d-comparison.json), and [diagnosis](nci-2026-10d-atom-diagnosis.json). The two archived metadata inputs remain unchanged. qaStats/MRDOC/legacy QA generation and insertion are excluded from this bounded replay.

## E23. QA and timestamps support a post-QA atom correction

Read-only inspection of the same hash-verified archive's QA reports explicitly found `VUndefinedTG_781756819 => FDA_2026_10D/`, `VUndefinedTTY_781756819 =>`, and the termgroup pattern error for atom 781756819. The archived QA statistics contain exactly one atom in the incomplete FDA termgroup.

Core inversion ended November 1 at 19:44:49 PST; QA ended at 20:24:11; the archived atom file mtime is 20:36:00. Thus the final corrected atom file was modified 11 minutes 49 seconds after QA. This substantially strengthens the earlier unverified-history assessment: a post-QA correction is strongly supported, and a manual edit is plausible. Neither operator identity nor the editing method/command is established. [Hashed excerpts and timeline](nci-2026-10d-post-qa-correction-evidence.json)

The unchanged generator's missing-PT defect remains reproduced; no candidate output or archived file was altered during this inspection. Fix it in the generator and retain a regression fixture rather than treating the official correction as nondeterminism or waiving the difference.

## E24. User accepts the manual post-QA correction as a working assumption

The user stated that she may confirm the edit with the inverter but authorized proceeding on the assumption that the inverter made it after reviewing QA. Record this as an accepted working assumption, with operator confirmation pending and nonblocking. The underlying QA/timestamp evidence remains E23; no new operator/audit evidence was obtained.

The next candidate should explicitly assign PT in the affected path and carry a first-original-code-PT regression fixture. The unchanged baseline's failed termgroup validation and raw comparison remain valid observations and are not waived by this historical explanation.

## E25. Explicit PT fix and regression checks

`fix/nci-explicit-pt` was created from the captured production baseline's planning commit, keeping the original baseline branch/tag unchanged. The sole transformation change is `tty => 'PT'` in `invert_NCI.pl:742`. A fixture runs the actual core inverter with three input orders, preferred terms with/without publisher codes, and a synonym. The unchanged baseline fails the two cold publisher-code-first cases; the fixed script passes all three, locally and on dev. Both versions were exercised on dev with networking disabled after verification of all 169 shared runtime files. Original publisher codes/CUIs and the synonym's SY type are asserted.

At the initial regression stage the source fix and fixture were uncommitted in the separate worktree, with full October replay pending. Subsequent commit, deployment to dev, and completed replay are recorded in E26–E27. No production deployment or official archive was changed. [Patch, hashes and regression results](nci-2026-10d-explicit-pt-fix.json)

## E26. Pinned explicit-PT candidate and preserved dev baseline

The tested source fix and regression fixture were committed locally as `0de8ca21158a2b1efa451ceff26809bbeaee20f9` on `fix/nci-explicit-pt`. Its full October core replay launched with networking disabled at the standard dev source path. E27 records the completed automatic comparison.

Before the source script/output was advanced, 24 prior baseline artifacts totaling 889,361,600 bytes were copied, hash-verified, and made read-only under the release's `etc/qa/replay-runs/baseline-core-20261103`. The new candidate has no seeded generated core output. Current publisher inputs, metadata fixtures and previously reproduced TREF files retain their declared hashes. The core engine commit and reused native-preparation commit are explicit separate fields. [Launch receipt](nci-2026-10d-explicit-pt-launch.json), [candidate request](nci-2026-10d-explicit-pt-case.json)

Seventeen comparison/corruption fixtures and twelve preservation/profile checks passed before that launch, including preservation failure without changing original files, complete read-only preservation before reset, missing preferred-term rejection, duplicate IDs, prohibited attribute-ID references, changed non-context records and missing metadata. The worker subsequently verified the new outputs and engine/input/runtime identities before reporting scoped core equivalence. Production and the official S3 archive are unchanged.

## E27. Explicit-PT full October replay passes

Commit `0de8ca21158a2b1efa451ceff26809bbeaee20f9` completed core inversion at 12:15:52 PST and automatic comparison at 12:17:25 on November 4. All 14 core-profile conditions pass. Atoms, relationships and merge facts match the official archive byte-for-byte. Context full-record multisets and attribute content/multiplicity match under the strictly scoped row-ID profile. All 796,203 non-CONTEXT attributes match including IDs. No undeclared termgroup remains. Inputs, engine and runtime reverified unchanged, and all 24 preserved baseline artifacts rehashed successfully after the run. [Result summary](nci-2026-10d-explicit-pt-summary.json)

The unchanged baseline failure remains historical evidence; the new generator produces the archived PT correction directly. This is core conversion coverage with archived metadata, not full release eligibility. The subsequent ordering proposal was first characterized locally across four seeds without a deployed library change; E28 records its separate committed candidate and full comparison. [Proposal evidence](nci-hierarchy-order-proposal.json)

## E28. Ordering candidate and stage-correct SNOMED reference

The independent ordering candidate `bfda2ce9b0d0ab23db3182d37aab4b1f5a13fd09` changes only the active Hierarchy::dumpCxtsAttrs emission loop to sorted keys. A seven-node/two-root/three-parent fixture produces identical context/attribute bytes across four seeds and preserves golden record content. It passes locally and on dev, as do the three PT inversion cases. The full October core comparison completed at 14:01:38 PST on November 4 with PASS_EQUIVALENT, all 14 profile conditions passing. Atoms/relationships/merges match byte-for-byte; context records and attribute content/multiplicity match under the scoped profile. The PT-only result and old shared runtime were preserved before the update and reverified after execution. [Ordering evidence](nci-2026-10d-context-order-fix.json), [full result](nci-2026-10d-context-order-summary.json)

An additional full-graph component seed check did not start because the authenticated SSH session ended. Four-seed fixture stability and the completed full-data comparison are established; full-data byte stability across different seeds is not yet established.

The SNOMED September reference is frozen read-only at its standard archive path, SHA-256 `61ff597f44a52da25928ad09691f4f2514e94069ac657f496677a2095b94095b`, 2,604,169,969 bytes, 120 members, and 25,929,050,786 expanded regular-file bytes. All five code/configuration files match the production snapshot. No candidate source folder was restored or inversion run. Sixteen required native/ICD inventory inputs are present; the absent complex-map file is optional in the inspected engine.

Archived `src/attributes.orig` is an exact prefix of `src/attributes.src`; all 1,133,725 added records are SEMANTIC_TYPE from E-SNOMEDCT_US_2026_09_01. The user confirmed these are added during insertion. The correct inversion oracle is therefore attributes.orig; the final file is a distinct enriched artifact. Keep the original SRC semantic type in comparisons. Both test/sty_term_ids and test/new_sty_defaults exist in the archive and belong to insertion-stage investigation, not required inversion inputs. [SNOMED contract](snomedct-us-2026-09-01-input-output-contract.json), [stage proof](snomedct-us-2026-09-01-attribute-stages.json)
