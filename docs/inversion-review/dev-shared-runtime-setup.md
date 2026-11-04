# Development shared-runtime setup

Completed 2026-11-03 14:16 PST on `ncias-d3777-c` as `tomcata`. The shared code comes from snapshot `production-snapshot-20261103`, commit `3b125edc1d29f7c7a91673da2a8d752bb0adff44`. This completes the shared-code/environment setup step; it does not constitute a full inversion replay.

## Installed layout

- `/local/content/MEME/MEME5/inv/INV`
- `/local/content/MEME/MEME5/inv/ENV`

Both directories were absent before setup. All **169 files** now match the pinned Git snapshot's SHA-256 values and captured permissions. No new operational root was introduced. The temporary same-directory staging trees were removed after atomic installation. Existing source/version folders and archive-tool files were not changed, and no OS packages or services were modified.

An installation receipt was deliberately added at `/local/content/MEME/MEME5/inv/installation-receipt.json` to identify the deployed commit, installed file hashes, profile backups and verification results. Its contents are also recorded in [dev-runtime-installation.json](dev-runtime-installation.json).

## Environment activation

Managed blocks in `tomcata`'s `.bash_profile` and `.cshrc` set `INV_HOME`, `ENV_HOME`, and `ENV_FILE`, then load the installed environment framework. Existing development settings remain in place. The blocks also apply the production inversion locale, collation, sort-compatibility setting, and inversion executable path. `TMP_DIR` remains `/tmp`; no scratch-path relocation was introduced. Java settings and application credentials were not copied from production.

Original profiles are retained in owner-readable backups:

- `/local/home/tomcata/.bash_profile.before-inversion-20261103T221401Z`
- `/local/home/tomcata/.cshrc.before-inversion-20261103T221401Z`

Fresh Bash and `tcsh` sessions both report the expected standard paths and settings. An already-open session can start a fresh `sudo su - tomcata` login to pick up the Bash activation. The installation was rerun to verify that matching trees are reused and the profile blocks are not duplicated or rewritten.

## Runtime verification

Checks ran with external networking unavailable in a temporary user/network namespace. No inversion constructor, native-data processing, QA/API metadata query, database operation, archive transfer, or source allocation was executed.

| Check | Result |
|---|---|
| Installed shared-file hashes and permissions | 169 verified |
| Fresh Bash environment | Passed |
| Fresh tcsh environment | Passed |
| `NLMInv`, bundled `Config::Properties`, and core Perl dependencies | Loaded from installed paths |
| `create_rolegroups.pl` | Perl syntax passed |
| `create_tref.pl` | Perl syntax passed |
| `delete_dup_tref_lines.pl` | Perl syntax passed |
| `tref_2_relational_files.pl` | tcsh syntax passed; the `.pl` suffix does not identify its interpreter |
| `invert_NCI.pl` | Perl syntax passed |
| Repeat installation | Reused verified code; no profile changes |

The first verification attempt exposed two errors in the bootstrap checks: a quoted Perl probe expression and use of Perl for the tcsh helper. Those checks were corrected; captured production files were not changed. The receipt preserves the first installation's backup provenance and records the subsequent successful validation.

## Reusable setup tools

[build_shared_runtime_bundle.py](../../tools/build_shared_runtime_bundle.py) constructs the shared-file bundle from a Git snapshot and verifies it against the snapshot manifest. [install_shared_runtime.py](../../tools/install_shared_runtime.py) checks the target host/account, refuses conflicting trees, installs missing code at the standard paths, backs up profile updates, and verifies the result. These are new bootstrap tools; they do not inherit the previous inversion-rework wrappers.

## Next step

The development S3-tool comparison is recorded in [archive-tool-comparison.json](archive-tool-comparison.json). The pull helper was subsequently updated with [reviewed acquisition options](archive-retention-change.md), and the October archive is frozen at the standard download path. Its [input/output boundary](nci-reference-boundaries.md) identifies October `src` as the reference and August as the saved metadata's low source. Native TREF outputs match exactly. The unchanged core exposed one missing PT and nondeterministic context ordering. Separate explicit-PT (`0de8ca2`) and ordering (`bfda2ce`) candidates each passed the full October core comparison offline; prior outputs and the old library were preserved and reverified. [Current result](nci-2026-10d-context-order-summary.json)

The current dev runtime has only `INV/lib/Hierarchy.pm` changed among the 169 shared files, recorded in `/local/content/MEME/MEME5/inv/candidate-runtime.json`. The initial installation receipt above describes the original baseline installation. QA/documentation generation still needs pinned historical metadata in place of live lookups. Legacy `INV_OLD` paths and the historical MTH Java environment remain future source-specific dependencies. The frozen SNOMED reference now has a [stage-specific contract](snomedct-us-2026-09-01-input-output-contract.json); its candidate has not run.
