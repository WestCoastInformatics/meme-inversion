# Development worker readiness

Inspected November 3, 2026. The user selected **ncias-d3777-c** and confirmed its storage is completely separate from production. SSH uses `shapirod2`; the read-only inspection ran as `tomcata`. Detailed observations are in [dev-worker-evidence.json](dev-worker-evidence.json).

The host passed the initial access, runtime, AWS authentication, S3 metadata-read, and namespace-creation checks. The shared `INV`/`ENV` trees are installed at the standard paths, both shell environments verified, and five selected NCIt scripts syntax-checked. The October NCIt archive is retained intact; the candidate was prepared by selecting declared inputs rather than restoring completed output. All three native TREF files reproduced exactly. The unchanged core exposed one FDA termgroup defect; separate explicit-PT and ordering candidates each passed their full October core comparison offline. The subsequent unchanged-production SNOMED core replay reproduced all five official files exactly. Its current shared runtime is restored baseline `3b125ed`, recorded in `inv/candidate-runtime.json`; the original installation receipt and NCIt candidate results remain historical. See [SNOMED result](snomedct-us-2026-09-01-baseline-summary.json). See [shared-runtime setup](dev-shared-runtime-setup.md), [reference boundaries](nci-reference-boundaries.md), and [current result](nci-2026-10d-context-order-summary.json). No database operation or OS package installation has been performed.

## Observed capacity and runtimes

| Item | Observation |
|---|---|
| Logical CPUs | 8 |
| RAM | 30.98 GiB total; 26.19 GiB available at inspection |
| Main disk | About 200 GiB total; 122.67 GiB available |
| Filesystem | Local XFS root volume |
| `/tmp` | About 15.5 GiB tmpfs; use disk-backed scratch for large jobs |
| Perl / Python | Perl 5.32.1 / Python 3.9.25 |
| Shell / sorting | tcsh 6.24.14 / GNU sort 8.32 |
| Java | Corretto 25; do not treat this as the historical MTH runtime |
| AWS CLI / Git | AWS CLI 2.36.47 / Git 2.50.1 |
| Container engines | Docker and Podman are absent |
| Namespace probe | An unprivileged user/mount/network namespace could be created successfully |

The production capture also reported Perl 5.32.1 and Python 3.9.25. This is useful compatibility evidence, not a complete dependency or behavior check. Java differs from the captured production default, and the historical MetamorphoSys runtime still requires explicit resolution.

The namespace probe records an available capability; it is not a decision to remap directories or require a container engine. The user directed the initial dev setup to mirror meme-edit's physical paths. The separate host and storage provide filesystem separation from production. Any additional process/network controls must preserve those paths; production metadata calls still require historical fixtures or explicit network restrictions before replay.

## Available reference archives

Read-only `ListObjectsV2` and `HeadObject` calls succeeded for these official objects in `nci-evs-meme`:

| Source version | Object key | Compressed size, GiB |
|---|---|---:|
| NCI_2026_10D | `inv/sources/NCI_2026_10D.tgz` | 0.509 |
| NCI_2026_09D | `inv/sources/NCI_2026_09D.tgz` | 0.508 |
| NCI_2026_08E | `inv/sources/NCI_2026_08E.tgz` | 0.506 |
| SNOMEDCT_US_2026_09_01 | `inv/sources/SNOMEDCT_US_2026_09_01.tgz` | 2.425 |
| MTH_2026AA | `inv/sources/MTH_2026AA.tgz` | 2.162 |

Exact sizes, last-modified values, and ETags are recorded in the evidence file. No object version ID was returned by these HEAD requests; this alone does not establish the bucket's versioning configuration. ETags are not content SHA-256 values. Freeze the downloaded bytes and record their SHA-256 when preparing a case.

Archive existence does not establish the required output stage, matching native inputs, historical metadata completeness, or expanded storage requirements. The existing free space looks promising for the first NCIt case; measure expanded inputs, reference/candidate outputs, and peak scratch requirements before accepting the capacity budget. The small MTH inversion archive does not include all external UMLS data behind its symlinks.

## Directory layout and access decisions

Mirror meme-edit's operational directory layout on `ncias-d3777-c`:

| Component | Standard development path, matching production |
|---|---|
| Shared inversion code | `/local/content/MEME/MEME5/inv/INV` |
| Shared environment framework | `/local/content/MEME/MEME5/inv/ENV` |
| Source releases | `/local/content/MEME/MEME5/inv/sources/<VSAB>` |
| NCImeta reference releases | `/local/content/MEME/MEME5/mr/ncim/<release>` |
| UMLS releases | `/local/content/MEME/MEME5/mr/umls/<release>` |
| Existing archive tools | `/local/content/MEME/MEME5/ncim/bin` |
| Shared NCIt QA helpers | `/local/content/MEME/MEME5/inv/archive/projects/TDE_QA` |

Keep each source's existing `orig`, `bin`, `etc`, `tmp`, `src`, and `insert` conventions and its declared links. There is no requirement for the dev and production servers to contain identical sets or counts of source/version folders. Select the current source and exact dependencies from the run configuration, reuse verified local folders, and restore required absent ones through the existing S3 tools. Extra folders are irrelevant; do not synchronize or clean them up to obtain directory parity.

The previously proposed separate replay root is withdrawn. Changing an operational path, introducing a remapped physical layout, or selecting a new location for test-only artifacts requires an explicit design decision with a reason and migration impact. Reference snapshots and candidate output must remain distinguishable, but their retention/layout is a test-apparatus decision, not a reason to move operational source folders by default. No new locations have been created.

The host's `/tmp` is tmpfs. Preserve existing configured temporary paths initially and assess capacity. Any override of `TMPDIR` or external-sort scratch must be deliberate and recorded rather than silently introduced during setup.

The dev S3 scripts have now been compared with the pinned production snapshot. `list_s3.csh` differs only in trailing whitespace. Dev's `pull_s3.csh` and `push_s3.csh` add explicit `AWS_PROFILE=meme` configuration, centralize bucket/path constants with the same values as production, and include an invalid-argument exit absent from production. Their core transfer steps and archive conventions otherwise agree. This establishes content differences, not file age or authorship. All three dev scripts pass syntax checks, and both `default` and `meme` profiles successfully read metadata for the October archive. See [the comparison record](archive-tool-comparison.json).

At the time of that comparison no script was replaced. The pull helper has subsequently been updated from the production reference with reviewed retention/download-only options and failure checks, after 12 isolated fixture cases passed. The acquisition used `AWS_PROFILE=meme` explicitly, retained the standard destinations, and froze the October archive. The list/push scripts remain unchanged; no upload ran. See [the retention change](archive-retention-change.md).

AWS authentication and the specific read calls were verified using the existing default configuration. Effective IAM permissions were not audited. Configure a read-only identity or scoped session for replay acquisition; successful read calls do not demonstrate that writes are prohibited. No credentials, credential values, or identity account details were copied into this repository.

## Next execution milestone

NCIt setup, unchanged-engine characterization, two separately pinned fixes, full core comparisons, and corruption/preservation fixtures are complete within their declared scope. Metadata acquisition, MRDOC/legacy QA, and insertion remain outside that result.

The unchanged SNOMED engine and original cleanup have also completed. All five official reference files match byte-for-byte, including attributes.orig. The original checker had two incomplete allowed-token lists; a source-backed review of its complete scan counters resolves those flags, with the raw result retained. The corrected checker has 25 passing fixtures locally and on dev. A subsequent full-file scan passes, with all five output hashes unchanged. [Result and review](snomedct-us-2026-09-01-baseline-summary.json)

1. Implement adapters from the common configuration and immutable lock to the characterized NCIt/SNOMED engines, using source-specific acceptance profiles over shared format/type definitions.
2. Complete the running MTH prepared-input replay and full comparison. Its archived subset, metadata and prior identity inputs are verified; this boundary needs neither historical Java nor an INV_OLD installation. Input regeneration is optional further coverage.
3. Keep historical metadata acquisition, MRDOC/legacy QA and insertion as explicit additional workflow coverage. Restore only declared dependencies and retain monitored resource reserves. SNOMED's observed 5.3 GiB peak is evidence for this one case, not a universal capacity guarantee.

These steps continue the [test architecture](test-architecture.md). The current tools provide source-specific characterization cases, not a provisioned general test service. MDR/RADLEX production discovery is captured separately; their replay and acceptance profiles remain pending.
