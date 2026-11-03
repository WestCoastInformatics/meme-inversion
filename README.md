# Production inversion code baseline

This tree captures the operational code on ncias-q3793-c under /local/content/MEME/MEME5/inv, the server location requested for the meme-edit modernization effort. Capture: November 3, 2026. Source provenance and exact inclusion/dependency records are in [baseline/manifest.json](baseline/manifest.json).

The import contains shared INV/ENV code, NCI October 2026 and its September variant, SNOMEDCT_US September 2026, MTH 2026AA scripts/configurations, top-level TDE QA helpers, and the existing list/pull/push S3 scripts. The source tree is constructed from production bytes rather than the previous inversion-rework branch. Existing source layouts and differences are retained for characterization.

Native packages, generated outputs, working intermediates, database exports, identity maps, and archive contents remain outside Git. Recorded symlinks preserve production topology; their external targets are not bundled. Never execute this snapshot against staff working directories. The next step is isolated development replay with declared data and runtime dependencies.

All imported files are hash-verified against the capture. Four files have documented credential redactions: two runbooks, one comment in a shell script, and the shell-profile template. The original hashes and transformations are in [baseline/sanitizations.json](baseline/sanitizations.json). Raw originals remain in a protected local capture outside tracked files. No transformation or QA logic was modernized in this import.

This is a code snapshot, not evidence of a successful replay. Some historical interpreter/INV_OLD/JRE paths are currently absent. Source versions were selected from scripts, logs and observed output/insertion artifacts; the installed NCImeta database state was not queried. See the manifest's known limits and [baseline/exclusions.json](baseline/exclusions.json).
