# Development replay retention

The default is short-lived test working data and compact milestone evidence. An unchanged successful comparison does not justify a permanent copy of every output, intermediate, log or executable capsule. The common configuration vocabulary, canonical release paths, official S3 archive process and actual prior-version dependencies are unchanged.

## Default lifecycle

1. Keep the active working candidate and only the prior data actually consumed by a run. Obtain official publisher/prepared/reference data from its established archive or cache; do not preserve another complete prior release merely to keep one identity map.
2. After conversion, comparison and independent verification succeed, retire superseded test bulk promptly. Outputs identical to an official reference need no extra permanent test copy. A reviewed correction needs its code, decision, expected hashes and regression coverage; its intermediate files need not remain forever because they differ from the old official archive.
3. Keep a compact milestone record: source/version, Git commit, input identities, output hashes, comparison/validation verdict and any reviewed exceptions. Routine identical reruns do not require permanent duplicate records or frozen Python module payloads. A retained result states what was checked at that time; discarding scratch files does not rewrite that verdict or promise the old working tree is still present.
4. Use a **30-day default expiry** for successful-run verbose logs, diagnostic files, redundant capsules and small retired-folder remnants. These are troubleshooting aids, not permanent evidence. Before expiry, retain any minimal excerpt or regression fixture needed to explain a milestone. Remove a residual folder and its lifecycle markers together so an incomplete marker cannot be mistaken for active data.
5. Keep failed-run bulk only while it is needed for an unresolved investigation. A hold needs an owner, reason and review date; review within 30 days. Once resolved or superseded by verified results, retire the bulk and apply the same short expiry to verbose evidence. A failure must not become permanent storage merely because it was once a failure.
6. Keep at most one rollback during replacement/verification. Finish retirement as part of closing that test cycle. Do not create another data archive or S3 upload to avoid making a retention decision. Required input/identity dependencies and staff's official release records follow their own lifecycle and remain protected.

`dev-test-bulk-retirement-v1` implements explicit retirement of obsolete common-test `.before-*` folders. Its externally pinned plan selects regular generated files under `src/` of at least 1 MiB, excluding QA/log/replay records. It permits discarding unneeded unique intermediates; this is intentionally **not lossless compaction** and does not claim the removed scratch bytes can be restored. Current working trees, live inputs, active jobs, incoming dependencies and holds block retirement. Small configuration and QA records remain temporarily, with the expiry above.

The current tooling provides bulk retirement and the original lossless compaction commands below. A scheduled expiry service has not been installed; the 30-day cleanup is an operator/work-cycle requirement. Do not claim that a timer has already purged logs, existing capsules, old exceptional archives or other source folders. This increment authorizes only the three identified obsolete MTH copies; it does not widen the deletion scope to unrelated data.

## Original lossless compaction mode

Policy `dev-replay-retention-v1` remains available when exact restoration of a retained tree is actually needed. Its conservative preservation rules below describe that mode, rather than a requirement to retain every successful test indefinitely.

1. Reuse the verified official archive and declared input caches. Keep actual prior-version data needed by the adapter, including NCIt's explicitly selected predecessor and MTH's prior CUI map.
2. Before replacing a dev working folder, retain it as one read-only rollback. **At most one uncompacted rollback from the new policy per source/version is allowed.** The common runner checks before creating a run or acquiring/staging data, and again before preservation. Another replay is blocked until that rollback has been reviewed/compacted; the runner never solves this by automatically creating an archive. Older frozen/standalone snapshots are reported separately as legacy backlog, so adopting the improved runner does not first require deleting historical investigations. A valid old common lock identifies old apparatus; a corrupt control cannot be reclassified as legacy to bypass the limit.
3. After the operation stops, plan lossless storage compaction. For accepted runs, bind the completed conversion/comparison, mandatory correction audits and independent verification as additional evidence. For failed attempts, preserve all failure records and mark the operation `PRESERVATION_ONLY_NO_RUN_ACCEPTANCE`; storage cleanup must not require a failed test to pass before it can be retried.
4. Plan duplicate-only compaction against the exact official current-version archive pinned in that run's lock. Remove a regular file only when the archive contains byte-identical contents at its original relative path. Preserve the original manifest, member mapping, permissions, nanosecond timestamps, checksums and verification identities in a small JSON record. Compaction never changes a run's acceptance or failed status.
5. Retain unique or changed files, manual edits, logs, QA records, links and empty directories in the existing retained folder. Corrected outputs that differ from the official archive stay. A completed, unchanged compacted folder does not consume the full rollback slot.

Lossless compaction removes redundant files without creating another `.tgz`/`tree.tar.gz`, copying the full tree elsewhere, or uploading to S3. It deliberately does not guess that an unmatched intermediate is reproducible. An explicit decision to discard obsolete test data uses bulk retirement instead; the default lifecycle above replaces indefinite preservation of every unmatched test file.

The receipt field `retained_unique_bytes` means bytes retained as protected or unmatched by this proof; it does not assert global uniqueness across every test folder. This first policy deduplicates exact same-path members of the pinned official archive. It does not deduplicate arbitrary corrected candidates against one another or guess equivalence between differently named files. The existing free-space gates still apply.

## Protection and recovery

Only `<reviewed-version>.before-<superseding-common-run-id>` is eligible. The tool always binds it to the terminal common operation, frozen lock and unchanged complete preservation receipt. A running/unfinished operation, unknown changes, current working folder, true prior release, changed archive or symlink root cannot authorize cleanup. Byte recovery is established independently of whether the semantic test passed.

Supplying an independent verification report and its SHA-256 additionally requires the accepted result and complete independently verified output hashes, and rechecks current accepted output bytes. Correction acceptance also requires the unchanged raw difference report and correction audit. A separate accepted MTH finalization review can satisfy this optional acceptance binding while preserving its original failed record. Without the report, the receipt explicitly makes no run-acceptance claim. Failed attempts retain all unique data, failure logs and QA; their archive-identical duplicates can still be reconstructed exactly.

Incoming links from other source trees and declared execution inputs block compaction. Files under `qa`/`logs`, replay records and `.log`/`.out`/`.err` files are retained even if identical to an archive member. A hold file at `qa/replay-retention/holds/<retained-folder-name>.json` blocks compaction and requires investigation; its human-readable contents should explain the reason. Releasing a hold is a deliberate maintenance decision, not a timeout.

Planning is read-only for source data and verifies every mapped archive member. Compaction rechecks its externally pinned plan, acceptance/verification records, the complete archive SHA-256 and the full retained tree. The unchanged archive hash preserves the original per-member proof without another decompression pass. A durable plan and durable existing provider archive precede deletion. The existing dev host/account guards, runtime lock and idle check apply. Interrupted cleanup retains the plan and remaining files; rerunning the same pinned operation can remove only the originally planned duplicates. An incomplete or changed compacted folder blocks subsequent replay admission.

`restore` reconstructs the original tree into a fresh allowed `.before-*` folder and checks every byte, mode, timestamp and link against the original manifest. It uses the existing official archive plus the unique files still retained locally. It cannot overwrite a canonical/current folder or any existing destination. Recovery may temporarily require expanded storage. As with the earlier archive helper, ownership, ACLs and extended attributes are outside the file/mode/topology contract.

The pinned official archive remains a recovery dependency for lossless compaction. These cleanup commands do not evict official archives, prior-version inputs or the prepared UMLS cache. A local archive cache can be evicted separately once exact pinned-byte recovery from S3 is supported and checked. A compacted tree needs reconstruction before an older verifier or rollback procedure that expects every original file in place; historical verification reports remain evidence of what was verified at their original execution time. A retired test tree is different: its obsolete scratch data has deliberately been discarded, and its original tree verifier is no longer a current lifecycle requirement.

## Common maintenance commands

For authorized obsolete test data, use the two-step retirement command:

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock retention-retire-plan \
  --run-id superseding-common-run --output retirement-plan.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock retention-retire-bulk \
  --plan-path SERVER_PLAN_PATH --plan-sha256 PLAN_SHA256 --output retirement-complete.json
```

Retirement uses a distinct `RETIRED_TEST_BULK` marker. Original success/failure records and earlier lossless cleanup receipts stay unchanged. Interrupted deletion can resume only against the same pinned file set. A changed tree or dependency fails closed. The compact completion record distinguishes discarded test bytes from archive-recoverable duplicates.

Use the current committed toolbox. New locks freeze the retention modules with the worker; older frozen apparatus remains historically unchanged and does not acquire the new limit retroactively. No production runtime activation is needed.

```sh
python3 -B tools/inversion_remote.py --socket /path/to/dev.sock retention-status case.lock.json --output retention-status.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock retention-plan \
  --run-id accepted-common-run \
  --verification /local/content/MEME/MEME5/inv/qa/path/to/final-verification.json \
  --verification-sha256 VERIFIED_REPORT_SHA256 --output retention-plan.json

python3 -B tools/inversion_remote.py --socket /path/to/dev.sock retention-compact \
  --plan-path SERVER_PLAN_PATH_FROM_PREVIOUS_RESULT \
  --plan-sha256 PLAN_SHA256_FROM_PREVIOUS_RESULT --output retention-complete.json
```

The plan reports duplicate file count/bytes and retained unique bytes. The original plan and completion receipt live at `qa/replay-retention/<retained-folder-name>/`; local outputs additionally identify the committed maintenance apparatus. For preservation without an acceptance claim, omit both verification arguments. This permits corrective reruns after failures. A folder with no removable duplicates can be recorded as unique/protected data with zero bytes freed; it is never falsely reported as deleted. No terminology-specific retention parameter names or inverter request changes are needed.

For recovery, the same interface provides `retention-restore --plan-path ... --plan-sha256 ... --destination /local/content/MEME/MEME5/inv/sources/<version>.before-<new-recovery-id> --output restored.json`. A restored full tree counts toward the rollback limit again. Maintenance can also invoke the frozen `tools/replay_retention.py` functions/CLI directly on dev.

The earlier [full-tree archive helper](retained-source-archives.md) remains an exceptional recovery tool for unique historical trees whose entire contents must be preserved. It is no longer the default response to repeated test runs. Existing verified archives are unchanged.

## Validation scope

`tools/check_retire_replay_bulk.py` passes 38 confined checks covering deliberate disposal of unique generated bulk, current/input/QA/log protection, encoded dependency aliases, external plan hashes, changed/held/unfinished trees, interruption/resumption and preservation of old lossless receipts. The updated existing retention and common-request suites pass 79 and 95 checks respectively. The actual MTH retirement and independent current-output/runtime postcheck are recorded below; local fixtures alone do not establish server cleanup.

`tools/check_replay_retention.py` exercises actual temporary filesystem operations, shared locking, common launch admission, unchanged/manual file protection, archive/member proof, all five source verdicts, separate MTH review, failed-test retry, failure before deletion, interrupted cleanup/resumption and complete reconstruction. Host/process activity is mocked in fixtures; the real content, permission, timestamp and filesystem checks are exercised. Its default mode also verifies the frozen maintenance transport; `--filesystem-only` requires no Git repository during a dev-side fixture run. The [fixture evidence](dev-retention-policy-fixtures-20261111.json) records 79 local checks under normal/restrictive permissions, 77 filesystem checks and 27 common-worker checks on dev, plus all eleven committed request variants. An initial fixture permission assumption was corrected for dev's restrictive umask; no transformation code changed.

Native conversion logic, official comparison rules, source-specific correction requirements, source scripts and data formats are unchanged. Local fixture passes do not establish that any existing dev folder has been compacted; actual server maintenance requires its own plan and completion receipts.

## Approved dev cleanup completed

The [completed plan summary](dev-retention-plans-20261111.json) binds the original byte-preserved [SNOMED plan](dev-retention-snomed-plan-20261111.json) and [MTH plan](dev-retention-mth-plan-20261111.json). After explicit user approval, apparatus `2b64e86` removed the exact 27 SNOMED duplicates (8,074,186,850 bytes) and 56 MTH duplicates (1,328,228,128 bytes). Together this is 83 files / 8.757 GiB. Protected/unmatched data remains in place. Both plans bind the original independent generated-settings verification, including MTH's separate accepted finalization review. [SNOMED completion](dev-retention-snomed-complete-20261111.json), [MTH completion](dev-retention-mth-complete-20261111.json).

The initial execution was prevented by automatic approval review before any deletion. The user's subsequent explicit approval authorized these two pinned plans, and both operations completed. Other folders remain outside this cleanup. No new archive, S3 upload, native inversion or source rewrite was performed.

The separate [read-only postcheck](dev-retention-postcheck-20261111.json), frozen at `7e1df37`, passes after independently rehashing all 67 retained regular files (14 SNOMED / 53 MTH), all 28 current output files, both official recovery archives, all 169 original shared runtime files and the required prior MTH CUI map. Retained file/link identities, permissions and timestamps, directory identities/modes, current entire-tree metadata and original acceptance/failure evidence are unchanged. Directory modification times affected by unlinking are recorded in the completion receipts. No full restoration copy was created. Thirteen independent-reader mutation checks also pass on dev.

Actual free space increased from 37.5 GiB to 46.3 GiB at the postcheck. Original per-member plan proofs plus unchanged complete archive hashes preserve recovery of the removed files. The [receipt identity manifest](dev-retention-completion-identities-20261111.json) binds eleven original JSON records and the fixture logs. The older full-tree verification reports remain historical evidence of their original executions; reconstruct a compacted predecessor before rerunning a verifier that expects every original file in place.

## Subsequent obsolete MTH bulk retirement

After the user's explicit retirement instruction, apparatus `d055112` discarded the 43 planned generated files in `MTH_2026AA.before-common-mth-clean-20261109`, `MTH_2026AA.before-common-mth-corrections-20261106` and `MTH_2026AA.before-common-mth-generated-20261110`. The [compact completion record](mth-bulk-retirement-20261111.json) binds all three plans and records 30,278,550,582 logical bytes removed, 4,418,555 small-file bytes retained and 46.9 GiB free after independent verification. Directory modes were restored; the current 134-entry MTH tree, all 23 accepted output hashes, both canonical prior maps, the independent prior cache, archive metadata and all 169 runtime files remained unchanged.

These were obsolete generated test copies; their bulk is deliberately discarded rather than newly archived. Their earlier run and cleanup records retain their original meanings at their original dates. Small remnants have a default expiry of December 11, 2026. The current accepted tree, actual prior inputs, official archive caches and unrelated older exceptional archives were outside this operation.
