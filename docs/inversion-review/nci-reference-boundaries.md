# NCIt October reference and replay boundaries

The completed official inversion archive was frozen on dev at 2026-11-03 15:02 PST. A fresh candidate has since been prepared at the standard release path, using only seven declared input files and pinned Git code. All three regenerated TREF files match the archived originals byte-for-byte. Core conversion completed successfully with networking disabled. Comparison is complete: two core files are byte-identical, contexts differ only in ordering, attributes differ only in generated row-ID assignment/order, and one atom has a substantive termgroup mismatch. This candidate fails acceptance. See the [comparison summary](nci-2026-10d-comparison-summary.json) and [preparation receipt](nci-2026-10d-candidate-preparation.json).

## Frozen reference

- Standard path: `/local/content/MEME/MEME5/inv/sources/NCI_2026_10D.tgz`
- Source object: `s3://nci-evs-meme/inv/sources/NCI_2026_10D.tgz`
- Compressed bytes: 546,021,953; expanded regular-file bytes: 4,147,680,334 (about 3.86 GiB).
- SHA-256: `c2332760cc014ddf462b5824b2b1ad720ca844871046753ed14d58fef5526bee`.
- Members: 104; links: 0.
- All 20 archived source-code/configuration entries match their originally captured production hashes. Credential-redacted runbook bytes are separately distinguished from the raw production hashes.

The archive is read-only and retained at the usual download location. S3 identity was checked before/after transfer and byte length verified. The server also has `.reference.json` and `.inventory.json` sidecars beside the archive. Their location is a deliberate provenance addition, not a relocation of code or release data. The [pull-helper change](archive-retention-change.md) passed 12 offline fixture checks before deployment. Its old dev copy was backed up, and the real acquisition used `AWS_PROFILE=meme`.

[Reference receipt](nci-2026-10d-reference.json), [full member inventory](nci-2026-10d-archive-inventory.json), and [metadata boundary review](nci-2026-10d-boundary-review.json) contain the exact details. Receipts include hashes, counts, and small diagnostic examples. Complete publisher datasets and `.src` file bodies remain on dev.

## Version and stage identity

The archive's `src/sources.src` explicitly contains `NCI_2026_10D` with low source `NCI_2026_08E`. This is saved preparation metadata supporting the August-to-October transition; it is not a query of today's database. September is not a required calendar predecessor for this case.

The user explicitly selected archived **`src`** as the reference. Archived `insert` contents and their preparation history are outside this replay's scope and do not block it.

The first replay targets **October `src`**, using its five core generated files:

| File | Archived newline count |
|---|---:|
| `classes_atoms.src` | 803253 |
| `attributes.src` | 1265611 |
| `relationships.src` | 1228468 |
| `mergefacts.src` | 595089 |
| `contexts.src` | 1185069 |

## Input/output boundary

| Role | Files | Treatment in a candidate |
|---|---|---|
| Publisher exports | Five October 26 annotation/object/class/relationship/hierarchy files under `orig/fromprovider` | Preserve as declared inputs; all five are present |
| Code and configuration | Pinned shared libraries/defaults and the October scripts/`nci.cfg` | Deploy from the Git baseline; archived hashes agree |
| Prepared source metadata | `src/sources.src`, `src/termgroups.src` | Legitimate declared input fixtures for this first characterization; metadata preparation is not tested by copying them |
| Role-group preparation | `tmp/rolegroups.tmp`, `orig/rels_needing_relgrp.txt` | Regenerate from publisher relationships |
| Temporary/final TREF | `tmp/*.TREF.tmp`, `orig/MRCONSO.TREF`, `orig/MRREL.TREF`, `orig/MRSAT.TREF` | Regenerate for the native-preparation test and compare to archived intermediate hashes |
| Five core `.src` files | Atoms, attributes, relationships, merges, contexts | Generate afresh; never extract these as candidate starting output |
| Auxiliary files | `code2merge`, relation summaries and scratch files | Regenerate in the same run |
| MRDOC, QA/statistics and insertion state | Archived documentation, reports and `insert` | Separate reference/coverage roles; exclude from initial conversion success claims |

Code tracing confirms that `NLMInv` opens source and termgroup metadata for reading while opening the five core `.src` files for writing. `invert_NCI.pl` uses normal overwrite mode, not append mode. Nevertheless, preparing a candidate from a full archive extraction would leave stale intermediates/reports and make checkpoints misleading. Prepare the standard source folder with an explicit input allowlist instead.

## First execution scope

The preferred first characterization regenerates role groups and TREF from the five native exports, checks those intermediates against the archive, then runs the unchanged core inverter using the declared archived source metadata. This covers native-data conversion under that supplied metadata. It does not establish reproduction of metadata acquisition/editorial decisions, live-lookup documentation generation, legacy QA, or insertion preparation.

The inspected native/TREF/core code reads no previous source folder. Its prior-version relationship is already encoded in the supplied metadata. Restore August/September folders only when a separately selected metadata-generation or QA stage actually requires their data. Neither extra dev folders nor absent unrelated releases affect this case.

The [machine-readable case contract](nci-2026-10d-input-output-contract.json) describes this bounded characterization, not an implemented general `inversion.json`/`case.lock.json` runner. `tools/prepare_nci_candidate.py` created the fresh candidate without copying any generated core output and saved stage receipts. The five preparation stages ran with networking disabled and exited successfully; all three TREF hashes match the archive.

The official atom file contains 803,253 unique, contiguous IDs from 781548593 through 782351845. These observed historical IDs constrain this isolated replay. They are not evidence of a production reservation limit; `nci.cfg` declares `SaidStart=781548593` without a `SaidEnd`. No production allocation is requested or consumed by the replay.

`tools/run_nci_core_replay.py` ran the unchanged inverter offline and compared all five fresh core files against the frozen October `src` hashes. It preserves existing run receipts rather than silently rerunning over a candidate. The bounded full-record comparison and structural/reference checks have now run. Complete domain validation and a general comparison apparatus remain separate work.

## Completed core comparison

The corrected core worker exited zero on November 3 at 16:29 PST after about 36 minutes. [Core receipt](nci-2026-10d-core-result.json), [full comparison](nci-2026-10d-comparison.json), [diagnosis](nci-2026-10d-atom-diagnosis.json), and [summary/verdict](nci-2026-10d-comparison-summary.json) preserve the results. Server reports are in the standard source folder's `etc/replay-core.json`, `etc/replay-comparison.json`, and `etc/replay-atom-diagnosis.json`. No candidate output was changed to achieve a match.

| Generated file | Rows in each file | Result |
|---|---:|---|
| `relationships.src` | 1,228,468 | Byte-identical |
| `mergefacts.src` | 595,089 | Byte-identical |
| `contexts.src` | 1,185,069 | Identical full-record multiset, including duplicates; row order differs |
| `attributes.src` | 1,265,611 | All content matches when only generated attribute row IDs are excluded; 796,203 non-CONTEXT records match including IDs |
| `classes_atoms.src` | 803,253 | One changed termgroup; every other row/field matches |

All 469,408 CONTEXT attributes have the same complete content and multiplicity. Of these, 469,407 have different row-ID assignments; the root CONTEXT record still matches exactly. Both attribute files have unique IDs spanning 1–1,265,611. Typed fields in the selected five files contain no attribute-ID references. The full attribute comparison includes endpoints, identifier types/qualifiers, values, flags, and digests. Raw differences remain visible; no whitespace, Unicode, flag, grouping, qualifier, trailing-field, or duplicate suppression is applied.

`Hierarchy.pm:785` iterates unsorted parent hash keys while emitting contexts and their attributes. This explains the observed ordering and associated generated-ID differences. It should become deterministic in a separately tested candidate change; broad ID exclusions are not a general acceptance policy.

### Substantive atom difference

At line 208,227, atom **781756819**, **AMPHIREGULIN**, code `7MGE0HPM2H`, source CUI `C1000`:

- Official archive: termgroup `FDA_2026_10D/PT`.
- Fresh dev output: termgroup `FDA_2026_10D/`.

The other 14 fields match. Prepared MRCONSO.TREF line 2 explicitly supplies `FDAPT` and an original code. This is the first subsource PT input. `invert_NCI.pl:742` omits `tty` in the original-code subsource PT branch, while line 628's other branch sets it. `$ptAtom` starts from an empty default and retains later values between calls. An offline, in-memory probe using the actual installed `Atom.pm` and combined pinned configuration reproduced the sequence: missing PT, explicit PT, retained PT. It opened no package output and reserved no IDs.

The archived file has the correct PT. A subsequent check of archived QA reports and timestamps now strongly supports a post-QA correction; the operator and whether it was manual or scripted remain unestablished. See the timeline below. The missing FDA termgroup is absent from `termgroups.src`; `FDA_2026_10D/PT` is declared. The five SRC termgroups absent from that per-source fixture are separately recognized by `QaTGs.pm:402-409` and are not new differences.

**Verdict: comparison complete; acceptance FAIL, review required.** Fix the missing `tty => 'PT'` in a new candidate revision with a first-record regression fixture. Preserve this baseline and its substantive difference rather than modifying its output or waiving the termgroup field.

### Validation and coverage

Fifteen corruption/ordering fixtures passed locally and on dev. Both file sets passed the scoped field-count, UTF-8, line-ending, trailing-field, atom-uniqueness, attribute-value-digest, and typed SRC_ATOM_ID endpoint/path checks. The external hierarchy root is permitted only because `nci.cfg` explicitly declares 31926003. The additional termgroup membership check found the one invalid FDA termgroup in the candidate. Structural success alone therefore does not establish valid output.

`sources.src` (60 rows) and `termgroups.src` (130 rows) remain byte-identical to their declared archived input fixtures; their generation was not tested. `qaStats.src` is an archived legacy-QA artifact and was not generated in this core run. Historical metadata acquisition, MRDOC/legacy-QA generation, insertion preparation, and insertion remain outside coverage.

### Initial attempt retained

The first attempt used an incorrectly short 1,200-second limit. The archived production core run took 2,247 seconds. The identified dev process was stopped and its partial outputs/logs/receipt preserved under `etc/qa/replay-attempt-001`. The clean restarted worker had a 7,200-second limit and completed successfully. Partial output from the interrupted attempt is not a compatibility result; the completed corrected run is the comparison candidate.

## Evidence of correction after QA

The archived QA error report explicitly flags this exact atom:

```text
****ERR: VUndefinedTG_781756819 => FDA_2026_10D/
****ERR: VUndefinedTTY_781756819 =>
```

The error report also contains `EValPat_781756819_3 => FDA_2026_10D/`, and the QA statistics count exactly one atom in that incomplete termgroup. `bin/invert.log` records `Done QA checks` after the final QA timing.

On **November 1, 2026, PST**:

| Event | Time |
|---|---|
| Core inversion finished | 19:44:49 |
| QA finished | 20:24:11 |
| Archived `src/classes_atoms.src` last modified | 20:36:00 |

The atom-file modification is 11 minutes 49 seconds after QA and 51 minutes 11 seconds after core inversion. QA therefore captured the original missing-PT defect, while the final archived atom contains PT. This strongly supports a correction after QA. A manual edit is plausible; timestamps and these logs do not establish the editor or command. [Hashed log excerpts and timestamp evidence](nci-2026-10d-post-qa-correction-evidence.json)

The migration should replace this record-order-dependent generator behavior with an explicit PT assignment and regression fixture. Any remaining QA-driven corrections should be recorded as reproducible changes with provenance and revalidation, rather than existing only in a completed source file.

## Accepted working assumption

On November 4, the user accepted the working assumption that the inverter manually added PT after reviewing QA, pending a possible confirmation with her. Confirmation is not a prerequisite for further migration work. This records an authorized assumption, not a newly verified audit fact.

Proceed by fixing the missing explicit PT assignment in a separate candidate revision and adding a regression fixture where the first subsource preferred term has an original publisher code. Keep the unchanged baseline, the failed termgroup check, and the raw comparison intact; accepting the historical explanation does not make the generated missing-PT record valid. Remaining QA-driven corrections should be explicit, reproducible, and followed by validation.

## Explicit-PT candidate fix

A separate worktree/branch, `fix/nci-explicit-pt`, now contains a one-line change to `sources/NCI_2026_10D/bin/invert_NCI.pl:742`: pass `tty => 'PT'` in the original-publisher-code PT path. It is based on the captured production baseline and is committed locally as `0de8ca21158a2b1efa451ceff26809bbeaee20f9`. The original snapshot, archived reference, and completed baseline output are preserved.

`tests/check_nci_pt_termgroups.py` runs the real core inverter on three small TREF/metadata fixtures: a publisher-code PT first, two publisher-code PTs before a no-code PT, and a no-code PT first. Each also checks that publisher codes/CUIs survive and a synonym remains SY. The first two cases fail against the unchanged baseline and all three pass with the fixed script, both locally and on dev. Dev execution used disabled networking and reverified 169 shared runtime files. No actual source-folder input/output was changed by these checks.

[Fix and regression evidence](nci-2026-10d-explicit-pt-fix.json) records the branch, worktree, hashes, exact patch, and results. The complete October replay finished successfully on dev and passed the scoped core equivalence checks. Deterministic hierarchy ordering is a separate candidate change.

## Committed candidate replay result

[Candidate request](nci-2026-10d-explicit-pt-case.json) pins commit `0de8ca2`. The core completed at 12:15:52 PST on November 4 and automatic comparison completed at 12:17:25. [Result summary](nci-2026-10d-explicit-pt-summary.json), [full result](nci-2026-10d-explicit-pt-result.json), and [status/preservation verification](nci-2026-10d-explicit-pt-status.json) preserve the evidence.

| File | Result against official October src |
|---|---|
| `classes_atoms.src` | Byte-identical, including FDA atom 781756819's PT |
| `relationships.src` | Byte-identical |
| `mergefacts.src` | Byte-identical |
| `contexts.src` | Identical full-record multiset with duplicates preserved; ordering differs |
| `attributes.src` | All content/multiplicity matches with the explicit generated row-ID diagnostic; 796,203 non-CONTEXT records match including IDs |

All 14 scoped acceptance conditions pass. This establishes the five core outputs under the supplied archived metadata, not full metadata acquisition, MRDOC/legacy QA, insertion or production release eligibility. The PT defect is resolved by the committed generator change, without editing output. Hierarchy serialization remains a separate change.

Before advancing the dev candidate, 24 baseline artifacts (889,361,600 bytes) were copied, hash-verified and made read-only under the same release's `etc/qa/replay-runs/baseline-core-20261103`. The preserved contents were independently rehashed successfully after completion. All operational paths remain standard. Native inputs, source metadata and verified TREF files were reused by declared hashes; the native-preparation engine reference is recorded separately from the new core commit. Engine/input/runtime hashes were verified again after execution.

The committed candidate worker and full result are under `etc/qa/replay-runs/explicit-pt-20261104`. `etc/replay-active-run.json` now reports completion and `PASS_EQUIVALENT`. Seventeen comparison/corruption fixtures and twelve preservation/profile checks passed. The profile requires exact atoms/relationships/merges, unchanged context multisets, matching unique attribute-ID allocations, unchanged non-CONTEXT records, no attribute-ID reference types, valid declared/framework termgroups, and structural/digest/reference checks. Production and the official S3 archive were unchanged.

## Completed hierarchy ordering candidate

A synthetic seven-node fixture with two roots and a descendant shared by three parents produces 11 context records and 12 CONTEXT attributes. Four Perl hash seeds give different raw ordering/IDs with the current emitter but the same full record contents. A temporary proposal that sorts only the active emission loop produces byte-identical contexts and attributes across all four seeds without changing their content. [Probe/proposal evidence](nci-hierarchy-order-proposal.json)

That proposal is now a separate committed candidate, `bfda2ce`, with the same four-seed regression passing locally and on dev. Its full October core comparison completed November 4 at 14:01:38 PST with **PASS_EQUIVALENT**: all 14 profile conditions pass. Atoms, relationships and merge facts are byte-identical to the archive. Full context records and all attribute content/multiplicity match; all 796,203 non-CONTEXT attributes also match including IDs. Historical context order and generated CONTEXT attribute IDs remain visible in the raw comparison. [Completed result](nci-2026-10d-context-order-summary.json)

The preserved PT-only result and old shared library were independently rehashed after the run. The full core was compared once for this candidate; byte stability across four hash seeds was verified on the regression fixture. An additional full-graph component check did not start because the SSH session expired. Full-data byte stability across seeds is therefore not claimed. Current SNOMED already uses its own sorted emission loop rather than calling this NCIt emitter; it still needs its own unchanged-engine replay and comparison profile.

[Ordering fix and regressions](nci-2026-10d-context-order-fix.json) and [launch receipt](nci-2026-10d-context-order-launch.json) record the actual second candidate. Before its shared-library update, the verified PT-only files and old Hierarchy.pm were copied/verified/read-only under `etc/qa/replay-runs/explicit-pt-core-20261104`. The active candidate runtime is recorded separately in `inv/candidate-runtime.json`; the initial installation receipt remains historical provenance. No other active core inversion is permitted while switching shared runtime code.

The subsequent unchanged-production SNOMED replay preserved this ordering-candidate library/receipt under its own `runtime-before` evidence, then restored all 169 baseline shared files. The NCIt results above remain historical evidence for their pinned engine/runtime. The current shared runtime is the baseline SNOMED engine, so a future ordering-candidate run must activate its matching library. [SNOMED result](snomedct-us-2026-09-01-baseline-summary.json)
