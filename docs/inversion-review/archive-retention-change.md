# Archive acquisition and retention change

Applied to the dev pull helper on November 3, 2026. The production snapshot remains unchanged. This is a reviewed change based on its `operations/ncim/bin/pull_s3.csh`, deployed at the existing `/local/content/MEME/MEME5/ncim/bin/pull_s3.csh` path on `ncias-d3777-c`.

## Behavior

The existing two-argument form still downloads, extracts, and removes an inversion archive after successful extraction. Two optional modes apply only to inversion archives:

```text
pull_s3.csh inv <VSAB> --keep-archive
pull_s3.csh inv <VSAB> --download-only
```

`--keep-archive` restores the folder and retains the downloaded archive. `--download-only` retains it without extraction, including when a source/version folder already exists. The latter is used to acquire the official reference before preparing candidate inputs.

Downloads use the existing bucket, archive names, and standard `inv/sources` location. No new replay root or alternate operational data paths were introduced. The retained archive and its `.reference.json`/`.inventory.json` sidecars are deliberate new test artifacts beside the standard download path. Candidate output remains distinct from the completed official files in that retained archive.

The helper now rejects invalid arguments, failed downloads, failed extraction, and attempts to overwrite an existing local archive. An extraction failure retains the archive for diagnosis. The inversion-object existence check uses AWS command status instead of looking for a `Metadata` field in the response. Legacy `.tar.gz` fallback remains supported. NCImeta/UMLS archive layout and transfer conventions were not redesigned.

`AWS_PROFILE` is standard calling-environment configuration; the acquisition job explicitly used `meme`, preserving the identity used by the old dev pull script without embedding a dev profile in the shared implementation. The AWS executable defaults to production's `/usr/bin/aws`; `AWS_BIN` is an explicit override used by the isolated fixture tests. No credentials or global AWS settings were changed. The list/push scripts were not replaced, and no upload command ran.

## Verification and provenance

[check_pull_s3.py](../../tools/check_pull_s3.py) exercised 12 cases with a fixture AWS executable and external networking disabled: download-only, retained extraction, legacy extraction/removal, failed download, failed extraction, invalid mode/flag combinations, existing-folder behavior, local-archive preservation, profile propagation, and legacy-extension fallback. Temporary test files were removed.

The old dev script was backed up beside the tool before atomic replacement. Its old/new hashes, backup location, fixture results, and source reference are in the [October acquisition receipt](nci-2026-10d-reference.json). A server-side tool receipt is at `/local/content/MEME/MEME5/ncim/bin/pull_s3.csh.reference-setup.json`.

[acquire_nci_reference.py](../../tools/acquire_nci_reference.py) then used that helper for the real download, checked object identity before/after transfer, verified byte length, made the archive read-only, and ran [inspect_inversion_archive.py](../../tools/inspect_inversion_archive.py). The audit streams and hashes members without extraction. The compressed SHA-256 identifies the actual frozen reference; the S3 multipart ETag is not treated as its content hash.

These bootstrap/acquisition tools and changes are in the local working tree and have not yet been committed. The data archive itself remains outside Git.
