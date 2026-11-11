# MTH preparation disposition corrections

This separate candidate changes three upstream preparation scripts. It does not change the running generated-settings inversion, its pinned `b2611ab` source engine, or any reviewed historical case. Historical source bytes remain available at that immutable Git revision. No change is deployed by committing this candidate.

## Disposition guessing

`guess.ncisources.spec.pl` used assignment in its `SPECIAL` branch. A prior row such as `BROKEN|BROKEN_1|--NEW?--|`, alongside a current publisher `BROKEN_2` record, exited successfully and emitted `BROKEN|BROKEN_2|SPECIAL|`. The downstream captured `genmmsysconfigs.pl` includes only `KEEP`, `UPDATE` and `NEW` sources in its selected-source list, so this silently recast row disappeared from that list.

Changing assignment to equality alone is insufficient: an unrecognized prior disposition can reuse the previous source's `$TYPE`. The candidate changes assignment to `eq` and adds an explicit failing `else` for an unrecognized matched prior disposition. Missing or unreadable prior decisions/publisher metadata are also rejected before producing output.

Valid behavior remains unchanged for all six known prior dispositions, current-version changes, MTH's required `UPDATE`, inherited termgroup exclusions, newly discovered sources requiring review, noncurrent publisher versions and removed sources. A new source still produces the existing `--NEW?--` review marker; this patch does not choose a disposition for it.

## Safe proposal publication

The existing `preinvert1.s` redirected guessed output directly over `ncisources.spec` and copied it to `.guessed`. Actual tcsh fixtures prove that a failed helper could leave a partial proposal and a successful final caller exit status.

The candidate caller checks the reported VSAB-preparation status before guessing. It then writes to a uniquely created candidate file in the release directory, captures diagnostic stderr separately, rejects failed or empty proposals, and publishes the complete candidate only after saving its matching `.guessed` review copy. A failed attempt preserves the existing `ncisources.spec`; its uniquely named candidate and `.stderr` evidence remain for inspection. The caller does not remove unrelated files.

The helper's successful output bytes and the successful `.guessed`/`ncisources.spec` bytes remain the same as before. Successful publication preserves an existing plan's permission bits; when no plan exists, it uses normal `0666 & ~umask` permissions. The `.guessed` copy receives the same mode. Portable Perl applies the mode only to the newly created candidate without changing the caller's umask. This is a proposal for the documented next human review step, not approval of newly discovered source decisions.

## Installed-source check

`ncisources.spec` stores the disposition in field 3. `preinvert2.s` checked field 2, the VSAB, so realistic `KEEP`/`UPDATE` rows contributed no expected source identities and missing installed sources went undetected.

The candidate uses field 3 in the existing validation command. A missing installed `KEEP` or `UPDATE` source now triggers the existing stop-and-review message. Valid installed sources still pass; the change does not require `NEW`, `EXCLUDE`, `REMOVE` or `SPECIAL` sources to exist in the inventory.

## Verification and scope

Run `python3 -B tools/check_mth_preparation_defects.py`. The [29-check fixture record](mth-preparation-corrections-fixtures-20261110.json) includes:

- Actual immutable historical Perl behavior, actual downstream subset-config selection and the equality-only patch's stale-value failure.
- Golden valid-case compatibility across all known dispositions and normal transitions.
- Actual revised `preinvert1.s` with a confined local VSAB stub, including success, helper failure, empty output and upstream reported failure.
- Preservation of a group-readable existing plan under a restrictive umask, plus three absent-plan umasks, with matching `.guessed` modes.
- The real disposition-validation commands, plus actual revised `preinvert2.s` against confined metadata API stubs, stopping before publisher preparation.
- Missing required helper inputs and separate retention of failed proposal data/diagnostics.

These fixtures never contact a database/server or run MetamorphoSys. They prove the narrow disposition checks and caller behavior, not full upstream publisher preparation. The already-running prepared-input conversion does not invoke these preparation scripts; it consumes its frozen prepared RRF and metadata inputs and retains its existing engine/apparatus identities. New upstream/native acceptance and release registration remain separate gates.
