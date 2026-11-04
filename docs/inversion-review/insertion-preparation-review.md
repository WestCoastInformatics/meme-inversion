# Insertion preparation: verified behavior

Inspected read-only on meme-edit (`ncias-q3793-c`) and dev (`ncias-d3777-c`) on November 3, 2026. Both have `/local/content/MEME/MEME5/ncim/bin/prep_insertion.csh`; their bytes match, SHA-256 `c89dfa7cb2f9fe0ab9ec491bc75c30546705bbf98585e5f734bd4b45296c3975`. The script was not executed.

The user correctly described its purpose. Default mode prepares `insert`; `-t <VSAB>` prepares `test`. For NCI and SNOMED (the non-MTH branch), it creates the target directory if absent, copies `src/*.src` and `src/*.RRF` unchanged, and recursively changes the target group to `tomcata`. The relevant copy commands are lines 92–93; there are no filtering, version-renaming, or transformation helpers.

For MTH it copies `src/*.src`, `src/MRDOC.RRF`, and `src/umlscui.txt`, then sets the group. Its comments explicitly include bequeathal relationship files in the `.src` set. This is a common staging process with a small MTH-specific file requirement, separate from the divergent inversion processes.

## Meaning for the October reference

The archived October `src` metadata names October with August low source. Its `insert` metadata instead names August with July low-source tags. Because preparation is copy-only, it cannot by itself introduce those version differences. The archived `insert` set does not correspond to the current October `src` set.

The exact explanation still requires the invocation history or later workflow steps: the directory may represent an earlier preparation, subsequently replaced data, or another retained working state. The inspection does not establish which happened. It would be incorrect to call the difference a transformation performed by `prep_insertion.csh` or to certify those files as the final October insertion package.

The first inversion replay therefore compares freshly generated core output against October `src` in the retained official archive. Insertion preparation is a separate downstream step, after the complete required package and validation evidence exist.

## Migration requirements supported by the code

The current script reuses a non-MTH target directory and does not remove old files before copying. Files no longer produced in `src` can remain in the target. It also does not explicitly stop/check each copy or group-change result before printing completion. These are observed code properties, not evidence that they caused this particular archive mismatch.

The replacement lifecycle should bind preparation to the validated source package's hashes, verify the complete target file inventory and byte identity, classify additions such as MTH's `umlscui.txt`, reject stale extra files, and record a preparation receipt. Preserve the standard `src`/`insert`/`test` locations unless a separate design decision changes them. A folder's name or an old completion message cannot establish which candidate it contains.

The exact [script captured from production](../../operations/ncim/bin/prep_insertion.csh) and [inspection evidence](insertion-preparation-review.json) are saved locally for version control. No production snapshot tag or server script was changed by this inspection.
