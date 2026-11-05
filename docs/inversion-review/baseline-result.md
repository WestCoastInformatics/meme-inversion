# Production code baseline result

Captured and imported locally on November 3, 2026. Production source files were only read. No inversion, S3 transfer, database operation, or production deployment was run.

| Item | Result |
|---|---|
| Branch | `baseline/meme-edit-20261103` |
| Snapshot tag | `production-snapshot-20261103` |
| Production import commit | `3b125edc1d29f7c7a91673da2a8d752bb0adff44` |
| Physical source | `ncias-q3793-c.nci.nih.gov:/local/content/MEME/MEME5/inv` |
| Capture interval | 2026-11-03T21:12:06.988928+00:00 to 2026-11-03T21:12:08.189737+00:00 |
| Imported production files/links | 285 |
| Credential-sanitized files | 4 |
| Baseline publication | Published by user; local origin tracking records baseline commit `bc085a3` |
| Functional replay | Original NCIt replay characterized; separate explicit-PT `0de8ca2` and ordering `bfda2ce` candidates passed full October core comparisons |

The production code tree was constructed from the fresh capture. No previous inversion-rework branch was merged or cherry-picked. The existing main checkout and earlier branch history are preserved. The production import and this planning record are separate commits.

## Included code

- Shared `INV` and `ENV` code, defaults, assets, and runtime libraries.
- NCIt `NCI_2026_10D` scripts/configuration and the distinct `NCI_2026_09D` variant.
- SNOMEDCT_US `SNOMEDCT_US_2026_09_01` scripts/configuration.
- MTH `MTH_2026AA` scripts, specifications, mapping/configuration inputs, compatibility links, and the effective `src/*.spec` variants.
- Ten top-level TDE QA helpers and the three existing list/pull/push S3 scripts.
- The shell profile as a credential-free environment template.

Before credential redactions, 153 imported entries matched existing Git main, 130 were absent from Git, and two differed. Production `INV/bin/api_metadata.sh` points to q3793 instead of q3000. Production `INV/bin/checkfields.pl` contains field-counting/Perl compatibility changes absent from main. The production versions were retained.

## Verification

All captured selections were rehashed on the server and were stable across capture. Every imported source file/link was checked against its recorded SHA-256, documented redaction where applicable, executable bit, and link target. The Git index and committed blobs were checked against an explicit path allowlist. The snapshot tag points to the dedicated production import commit.

Four files required credential removal: the two NCIt runbooks, a login comment in MTH `invert2.s`, and database aliases in the shell-profile template. Transformations and both original/imported hashes are recorded in the baseline branch's `baseline/sanitizations.json`. No transformation or QA statements were changed. Raw originals and the full excluded-data inventory remain in the ignored, owner-access-only `.baseline-private/20261103T211206Z/raw` directory in the original workspace.

The baseline branch contains `baseline/manifest.json`, `baseline/repository-comparison.json`, and `baseline/exclusions.json`. Native data, outputs, logs, saved database/identity exports, distribution archives, and external link targets were excluded from the code import. An environment log and three historical/experimental TDE files were excluded explicitly after capture. The main checkout's mutable allocation/export files and old distribution archive were not inherited into the new code tree.

## Remaining work

This snapshot establishes code provenance, not a completed historical replay. Current filesystem checks found absent `/site/bin/perl`, `INV_OLD` entry points, and the bundled MTH JRE path. Runtime defaults were inventoried but do not establish the exact historical MetamorphoSys environment. Resolve these dependencies through verified production/history artifacts before execution; do not silently substitute old project code.

The source folders have execution and output/insertion artifacts, but the current installed NCImeta source state was not queried. The meme-edit web name resolves through a load balancer, so the recorded authoritative physical location is the server/path explicitly supplied by the user.

The user selected `ncias-d3777-c` with separate storage. Shared code and the NCIt baseline/fixed-candidate replays are established at the standard paths. The SNOMED baseline has now also run: all five official core files reproduced byte-for-byte, with inversion attributes mapped to archived `attributes.orig`. A separate review corrects two allowed-token omissions in the new validator; the original scan remains intact. [SNOMED result](snomedct-us-2026-09-01-baseline-summary.json) MTH and full metadata/QA/insertion coverage remain future work. Extra or fewer unrelated release folders do not matter. Continue with [the shared-runtime setup](dev-shared-runtime-setup.md), [the test architecture](test-architecture.md), and [SNOMED contract](snomedct-us-2026-09-01-input-output-contract.json).

## Subsequent NCIt replay result

The [committed explicit-PT candidate](nci-2026-10d-explicit-pt-summary.json) passed the full October core comparison on November 4. It corrects the one missing FDA term type reproduced from the unchanged production snapshot; that original baseline and its files remain preserved. The separate [ordering candidate](nci-2026-10d-context-order-summary.json) also passed its full core comparison and four-seed serialization fixture. Context/attribute content matches under the scoped ordering/generated-ID profile. Metadata acquisition, MRDOC/legacy QA and insertion remain outside these acceptance results.
