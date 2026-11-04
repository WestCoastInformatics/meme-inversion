# Production inversion code baseline

This tree captures the operational code on ncias-q3793-c under /local/content/MEME/MEME5/inv, the server location requested for the meme-edit modernization effort. Capture: November 3, 2026. Source provenance and exact inclusion/dependency records are in [baseline/manifest.json](baseline/manifest.json).

The import contains shared INV/ENV code, NCI October 2026 and its September variant, SNOMEDCT_US September 2026, MTH 2026AA scripts/configurations, top-level TDE QA helpers, and the existing list/pull/push S3 scripts. The source tree is constructed from production bytes rather than the previous inversion-rework branch. Existing source layouts and differences are retained for characterization.

Native packages, generated outputs, working intermediates, database exports, identity maps, and archive contents remain outside Git. Recorded symlinks preserve production topology; their external targets are not bundled. Never execute this snapshot against staff working directories. The next step is isolated development replay with declared data and runtime dependencies.

All imported files are hash-verified against the capture. Four files have documented credential redactions: two runbooks, one comment in a shell script, and the shell-profile template. The original hashes and transformations are in [baseline/sanitizations.json](baseline/sanitizations.json). Raw originals remain in a protected local capture outside tracked files. No transformation or QA logic was modernized in this import.

This is a code snapshot, not evidence of a successful replay. Some historical interpreter/INV_OLD/JRE paths are currently absent. Source versions were selected from scripts, logs and observed output/insertion artifacts; the installed NCImeta database state was not queried. See the manifest's known limits and [baseline/exclusions.json](baseline/exclusions.json).

## Characterization and replay tools

This branch adds the development replay/comparison apparatus and review evidence to the production-derived code. The two transformation changes remain separate ancestor commits: explicit PT assignment (`0de8ca2`) and stable hierarchy emission (`bfda2ce`). The untouched production snapshot/tag and original failed replay remain the baseline.

NCIt October native preparation reproduced all three archived TREF files exactly. Both fixes passed complete offline comparisons of the five generated core files against the frozen official archive, using explicitly declared archived source metadata. Atoms, relationships and merge facts are byte-identical; context and attribute content pass the documented order/generated-ID comparison profile. [Current result and limits](docs/inversion-review/nci-2026-10d-context-order-summary.json)

The tools in `tools/` currently characterize this NCIt case at the mirrored dev paths. They are source-specific scaffolding for the [common configuration and adapters](docs/inversion-review/configuration.md), which are not yet a general runner. Metadata acquisition, MRDOC/legacy QA, insertion and production release eligibility are outside the passing case. Remote tools enforce the selected dev host/account; they must not be redirected into staff working directories. Preservation precedes candidate replacement, and prior run receipts identify the apparatus bytes actually executed.

The SNOMED September archive is frozen and inventoried; its candidate has not run. Its [reference contract](docs/inversion-review/snomedct-us-2026-09-01-input-output-contract.json) maps generated `attributes.src` to archived `src/attributes.orig`, before insertion adds semantic types. The NCIt generated-ID rules are not automatically valid for SNOMED or MTH. Full-graph byte stability across hash seeds has not been checked; the committed four-seed hierarchy regression uses a synthetic graph and the actual serializers.

Run the local regression checks from this checkout:

```sh
python3 -B tools/check_core_comparison.py
python3 -B tools/check_nci_replay_advance.py
python3 -B tests/check_nci_pt_termgroups.py
python3 -B tests/check_nci_hierarchy_order.py
python3 -B tools/check_snomed_replay.py
```

These checks use temporary synthetic inputs and do not require server access. The S3 pull helper's separate dev-only fixtures are in `tools/check_pull_s3.py`; twelve cases passed during archive-tool setup. `operations/ncim/bin/prep_insertion.csh` is a captured reference, not an insertion command run by this apparatus. See the [assessment and phased priorities](docs/inversion-review/assessment.md) for the broader migration plan.

The SNOMED preparation/worker/comparator modules now support the September unchanged-production case through an explicit locked package. They select eighteen archived inputs and five Git code/configuration files, preserve the current dev library/receipt before restoring the baseline shared runtime, run conversion and original attribute cleanup offline with monitored capacity limits, and compare all five outputs without ignoring generated identifiers. Twenty-three local fixtures cover reference-stage mistakes, generated-output seeding, structural/content defects and runtime preservation failures. A completed SNOMED result must be recorded separately; the presence of these tools is not evidence that its inversion has run.
