# Development replay retention

Policy `dev-replay-retention-v1` prevents full test working folders accumulating after successive replays. It applies to the common dev runner for all five reviewed sources. The seven operator request fields, canonical release paths, official S3 archive process and actual prior-version dependencies are unchanged.

## Default lifecycle

1. Reuse the verified official archive and declared input caches. Keep actual prior-version data needed by the adapter, including NCIt's explicitly selected predecessor and MTH's prior CUI map.
2. Before replacing a dev working folder, retain it as one read-only rollback. **At most one uncompacted rollback from the new policy per source/version is allowed.** The common runner checks before creating a run or acquiring/staging data, and again before preservation. Another replay is blocked until that rollback has been reviewed/compacted; the runner never solves this by automatically creating an archive. Older frozen/standalone snapshots are reported separately as legacy backlog, so adopting the improved runner does not first require deleting historical investigations. A valid old common lock identifies old apparatus; a corrupt control cannot be reclassified as legacy to bypass the limit.
3. After the operation stops, plan lossless storage compaction. For accepted runs, bind the completed conversion/comparison, mandatory correction audits and independent verification as additional evidence. For failed attempts, preserve all failure records and mark the operation `PRESERVATION_ONLY_NO_RUN_ACCEPTANCE`; storage cleanup must not require a failed test to pass before it can be retried.
4. Plan duplicate-only compaction against the exact official current-version archive pinned in that run's lock. Remove a regular file only when the archive contains byte-identical contents at its original relative path. Preserve the original manifest, member mapping, permissions, nanosecond timestamps, checksums and verification identities in a small JSON record. Compaction never changes a run's acceptance or failed status.
5. Retain unique or changed files, manual edits, logs, QA records, links and empty directories in the existing retained folder. Corrected outputs that differ from the official archive stay. A completed, unchanged compacted folder does not consume the full rollback slot.

This removes redundant files without creating another `.tgz`/`tree.tar.gz`, copying the full tree elsewhere, or uploading to S3. It deliberately does not guess that an unmatched intermediate is reproducible. Unique retained files can still consume space and require a reviewed decision if no longer useful. There is no age-based deletion or automatic deletion of accepted unique results.

The receipt field `retained_unique_bytes` means bytes retained as protected or unmatched by this proof; it does not assert global uniqueness across every test folder. This first policy deduplicates exact same-path members of the pinned official archive. It does not deduplicate arbitrary corrected candidates against one another or guess equivalence between differently named files. The existing free-space gates still apply.

## Protection and recovery

Only `<reviewed-version>.before-<superseding-common-run-id>` is eligible. The tool always binds it to the terminal common operation, frozen lock and unchanged complete preservation receipt. A running/unfinished operation, unknown changes, current working folder, true prior release, changed archive or symlink root cannot authorize cleanup. Byte recovery is established independently of whether the semantic test passed.

Supplying an independent verification report and its SHA-256 additionally requires the accepted result and complete independently verified output hashes, and rechecks current accepted output bytes. Correction acceptance also requires the unchanged raw difference report and correction audit. A separate accepted MTH finalization review can satisfy this optional acceptance binding while preserving its original failed record. Without the report, the receipt explicitly makes no run-acceptance claim. Failed attempts retain all unique data, failure logs and QA; their archive-identical duplicates can still be reconstructed exactly.

Incoming links from other source trees and declared execution inputs block compaction. Files under `qa`/`logs`, replay records and `.log`/`.out`/`.err` files are retained even if identical to an archive member. A hold file at `qa/replay-retention/holds/<retained-folder-name>.json` blocks compaction and requires investigation; its human-readable contents should explain the reason. Releasing a hold is a deliberate maintenance decision, not a timeout.

Planning is read-only for source data and verifies every mapped archive member. Compaction rechecks its externally pinned plan, acceptance/verification records, the complete archive SHA-256 and the full retained tree. The unchanged archive hash preserves the original per-member proof without another decompression pass. A durable plan and durable existing provider archive precede deletion. The existing dev host/account guards, runtime lock and idle check apply. Interrupted cleanup retains the plan and remaining files; rerunning the same pinned operation can remove only the originally planned duplicates. An incomplete or changed compacted folder blocks subsequent replay admission.

`restore` reconstructs the original tree into a fresh allowed `.before-*` folder and checks every byte, mode, timestamp and link against the original manifest. It uses the existing official archive plus the unique files still retained locally. It cannot overwrite a canonical/current folder or any existing destination. Recovery may temporarily require expanded storage. As with the earlier archive helper, ownership, ACLs and extended attributes are outside the file/mode/topology contract.

The pinned official archive remains a recovery dependency. This policy never evicts official archives, prior-version inputs or the prepared UMLS cache. If a cache must be removed separately, first establish recovery of its exact pinned bytes from S3. A compacted tree needs reconstruction before an older verifier or rollback procedure that expects every original file in place; historical verification reports remain evidence of what was verified at their original execution time.

## Common maintenance commands

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

`tools/check_replay_retention.py` exercises actual temporary filesystem operations, shared locking, common launch admission, unchanged/manual file protection, archive/member proof, all five source verdicts, separate MTH review, failed-test retry, failure before deletion, interrupted cleanup/resumption and complete reconstruction. Host/process activity is mocked in fixtures; the real content, permission, timestamp and filesystem checks are exercised. Its default mode also verifies the frozen maintenance transport; `--filesystem-only` requires no Git repository during a dev-side fixture run. The [fixture evidence](dev-retention-policy-fixtures-20261111.json) records 79 local checks under normal/restrictive permissions, 77 filesystem checks and 27 common-worker checks on dev, plus all eleven committed request variants. An initial fixture permission assumption was corrected for dev's restrictive umask; no transformation code changed.

Native conversion logic, official comparison rules, source-specific correction requirements, source scripts and data formats are unchanged. Local fixture passes do not establish that any existing dev folder has been compacted; actual server maintenance requires its own plan and completion receipts.

## Approved dev cleanup completed

The [completed plan summary](dev-retention-plans-20261111.json) binds the original byte-preserved [SNOMED plan](dev-retention-snomed-plan-20261111.json) and [MTH plan](dev-retention-mth-plan-20261111.json). After explicit user approval, apparatus `2b64e86` removed the exact 27 SNOMED duplicates (8,074,186,850 bytes) and 56 MTH duplicates (1,328,228,128 bytes). Together this is 83 files / 8.757 GiB. Protected/unmatched data remains in place. Both plans bind the original independent generated-settings verification, including MTH's separate accepted finalization review. [SNOMED completion](dev-retention-snomed-complete-20261111.json), [MTH completion](dev-retention-mth-complete-20261111.json).

The initial execution was prevented by automatic approval review before any deletion. The user's subsequent explicit approval authorized these two pinned plans, and both operations completed. Other folders remain outside this cleanup. No new archive, S3 upload, native inversion or source rewrite was performed.

The separate [read-only postcheck](dev-retention-postcheck-20261111.json), frozen at `7e1df37`, passes after independently rehashing all 67 retained regular files (14 SNOMED / 53 MTH), all 28 current output files, both official recovery archives, all 169 original shared runtime files and the required prior MTH CUI map. Retained file/link identities, permissions and timestamps, directory identities/modes, current entire-tree metadata and original acceptance/failure evidence are unchanged. Directory modification times affected by unlinking are recorded in the completion receipts. No full restoration copy was created. Thirteen independent-reader mutation checks also pass on dev.

Actual free space increased from 37.5 GiB to 46.3 GiB at the postcheck. Original per-member plan proofs plus unchanged complete archive hashes preserve recovery of the removed files. The [receipt identity manifest](dev-retention-completion-identities-20261111.json) binds eleven original JSON records and the fixture logs. The older full-tree verification reports remain historical evidence of their original executions; reconstruct a compacted predecessor before rerunning a verifier that expects every original file in place.
