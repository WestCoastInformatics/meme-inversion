# Baseline the operational code in Git

Status: production capture and local Git import completed November 3, 2026. The snapshot is hash-verified; functional replay remains pending. See [the baseline result](baseline-result.md).

The starting point is the operational deployment on meme-edit. Preserve the existing repository and earlier branch history while constructing the baseline code tree solely from verified production files. The earlier project-rework branches are informative only. This procedure implements the [starting-point decision](assessment.md#implementation-starting-point-operational-code-on-meme-edit).

## 1. Identify the exact operational code set

Confirm the physical host and paths behind meme-edit and identify the entry points actually used by staff for each source. Record the selected NCI, SNOMEDCT_US, and MTH release directories, whether each run is completed or in progress, and any shared installations or external tools they invoke. Use staff run records and script/configuration references to establish what is active; selecting the newest directory is insufficient.

The existing assessment captured code from `ncias-q3793-c`. Reuse that inventory to narrow the work, then verify it against the selected operational deployment. The observed match between 39 shared modules and repository main does not cover all scripts, source-specific configurations, specifications, mappings, or environment dependencies.

**Result:** an explicit list of authoritative source paths and selected release versions, with unresolved selections recorded rather than guessed.

## 2. Capture a read-only production snapshot

Collect shared libraries and utilities, source-specific scripts, `.cfg`/`.spec` files, representation mappings, defaults, and operational runbooks. Include relevant environment/runtime requirements and the dependency identities of the existing S3 tools. Record interpreter/tool versions and external package identities needed to execute the code. Record symlink targets without blindly following links into large native datasets.

Preserve relative paths and file bytes in the capture. Record source host/path, capture time, size, SHA-256, executable status, and symlink target where applicable. Record the capture interval and check for files changing during collection; repeat affected captures if staff edits them. Production collection remains read-only and does not require stopping inversion work.

Keep publisher datasets, generated `.src` outputs, working intermediates, logs, and archives in their existing storage system. Record their artifact/dependency identities separately. Where an environment file contains credentials, retain the original securely outside Git and commit a documented sanitized template; record that transformation explicitly instead of claiming byte identity for the template.

**Result:** a preserved production capture plus a machine-readable file/dependency manifest.

## 3. Compare the capture with the repository

Classify every selected component as identical to a tracked file, different, absent from Git, or external. Also identify tracked files that are outside the approved production code set. The current main checkout contains the shared `INV` tree and a distribution archive; it does not establish a complete operational baseline for the three source workflows.

For source scripts that differ across release folders, retain the selected original variants and their provenance. Do not merge them, update dates, remove hardcoded values, fix QA, or normalize formatting during the baseline import. For example, the observed NCIt September/October subsource differences need to remain visible until deliberately migrated to configuration.

If a shared S3 tool already has a maintained repository, pin that repository/version and verify its content against the deployment. Otherwise preserve its captured code and establish its repository ownership before relying on a mutable server copy. A bare path or hash without a retrievable implementation is not a complete dependency.

**Result:** a reviewed import list and difference report, including external or unresolved dependencies.

## 4. Import through a separate checkout and baseline branch

Use the existing `WestCoastInformatics/meme-inversion` repository with a separate checkout/worktree and a dedicated branch, such as `baseline/meme-edit-YYYYMMDD`. Preserve the current working copy, the untracked planning documents, main, and earlier branches. No history rewrite is needed to establish a clean production code baseline.

Construct the imported code tree from the approved production manifest. A branch's ancestry must not cause unverified repository files to remain in the baseline tree. Import shared code and source-specific variants with a source-to-repository path map; preserve their original layout initially wherever practical. Keep retained release variants distinguishable rather than flattening different folders into one unreviewed script.

Use an explicit file allowlist. Add ignore rules for native packages, release outputs, temporary files, and local credentials. Commit the production code and its provenance as a dedicated import commit. Keep planning material and later modernization changes in separate commits. The exact staging layout is chosen after the import inventory so moving files cannot silently change what gets imported.

**Result:** a reviewable production import commit, without changes to production execution.

## 5. Verify and mark the captured baseline

Compare repository blobs against the manifest, accounting for the declared path map and any explicitly sanitized templates. Check executable bits and symlink targets, and ensure all selected components are included or explicitly pinned externally. Confirm that no unapproved files from prior project work entered the code tree.

Review the resulting file list and unresolved dependencies with the inversion owner. Then create an annotated snapshot tag, such as `production-snapshot-YYYYMMDD`, identifying the source deployment and manifest. Publishing the branch/tag makes this baseline available for review and development. File verification establishes snapshot fidelity; it does not yet establish successful execution or data correctness.

**Result:** an immutable, identifiable snapshot with a complete inclusion/exclusion/dependency record. Outstanding runtime or artifact gaps remain explicit.

## 6. Establish an unchanged-engine replay

On the isolated development worker, run that baseline with matching native inputs, prior-state data, historical metadata, ID settings, and an official archived result. Start with one well-documented NCIt case, then add SNOMED and MTH cases. Match the output stage and code/input provenance before attributing a difference to the engine. Older references may require their original archived production code as a separate reference-engine identity.

Put path/runtime compatibility support outside the frozen baseline where possible. Any necessary code adjustment is a subsequent, separately reviewed commit and is identified as such. Record unresolved reproduction limits rather than silently filling them from current database state. The [test architecture](test-architecture.md) defines independent validation and comparison requirements.

**Result:** recorded replay evidence establishing what the imported baseline can reproduce. A Git snapshot alone is not a tested baseline.

## 7. Branch modernization work from the baseline

Begin implementation from the production import commit, retaining its snapshot tag as a stable reference. Introduce the common configuration adapters, lifecycle changes, validation fixes, and transformation replacements in small changes with explicit comparison evidence. Keep the frozen import intact so every candidate can be traced back to the production starting point.

The immediate work is steps 1–3: confirm the operational code set, capture it, and produce the import/difference manifest. They make the first Git import concrete without changing staff's inversion work.
