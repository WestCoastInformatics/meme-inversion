# NCIt installed-state acquisition: captured evidence and gaps

The local production capture establishes several preparation formats and consumers, but does not contain a trustworthy complete installed-state capture. No database query, API call, server job or new exporter was run for this review. No installed-state snapshot has been acquired, and no assembler was implemented. The [machine-readable gap record](nci-state-acquisition-gaps.json) binds the reviewed files by SHA-256.

The existing [NCIt release preflight](nci-release-preflight.md) remains usable with explicitly supplied, reviewed frozen state. Its synthetic fixtures demonstrate validation behavior; they do not establish that the required historical or current installed-state data exists. We should acquire the actual export producer and its identity semantics before implementing an assembler.

## What the captured code establishes

| Captured evidence | Supported meaning | Limit |
|---|---|---|
| `INV/bin/api_metadata.sh:58–59,151–155` | `current_sources` calls `/metadata/terminology/current`, then emits `RSAB\|VSAB` text from terminology/version fields. | No family, root SAID, or complete termgroup inventory is exported. The wrapper transforms names, discards the raw payload, and removes temporary response files. It is a current-service answer, not an October historical snapshot. |
| `INV/lib/QaSrcs.pm:83–94,151–152,197–204` | QA compares proposed `low_source` with current source-version answers. | The QA consumer does not prove source-root existence or provide installation provenance for archived preparation files. |
| `INV/lib/QaAtoms.pm:69–80,610–623` | QA uses current source abbreviations to flag regenerated root records and recognizes `SRC/RPT` and `V-<source>` in `.src` records. | Existing source metadata is used as a proxy; this is not an export of installed root atom identities. Its code splitting on hyphens is also insufficient as a general source-identifier parser. |
| `INV/lib/QaTGs.pm:48–81,236–237,269–277` | Historical low-termgroup lookup SQL and checks are explicitly disabled after the M5 migration. | Commented Oracle-era code cannot define a working M5 export or current schema. |
| `sources/NCI_2026_10D/etc/README.INVERSION:23–31` | The workflow dumps a source template, edits it, renders `sources.src`, and copies/updates `termgroups.src`. | Resulting files describe the proposed release. They cannot establish what was installed before it. The referenced `dump_src_info.pl` producer is missing from the captured repository. |
| `INV/bin/make.sources.src.pl:8–24,27–55` and `INV/etc/sources.src.template:13–32` | The renderer and template establish the 20 preparation fields, including stripped source, version and source family. | They establish file meaning, not database column meaning or installation state. Family assignments and replacement-source selection still need reviewed transition policy. |
| `INV/bin/SRCbuilder.pl:225–235` | New SRC/RPT and SRC/RAB records receive source atom IDs and codes `V-<stripped source>`. | Newly generated IDs and saved `HC.RootNodeSaid` values cannot substitute for an installed SRC/RPT root export. |
| `sources/NCI_2026_10D/bin/nci_2017_06d.csh:1085–1094` | Older insertion code distinguishes `source_id_map.source_row_id` from `local_row_id`/`classes.atom_id`. | This query concerns semantic-type extraction, not root capture, and its backend currency is not established. Copying `classes.atom_id` into a source-atom-ID field would be unsupported. |
| `INV/bin/extract_metadata.sh:66–94` | The extraction wrapper saves RELA inverses, expanded forms and term-type classifications. | It exports neither installed source roots nor a complete installed termgroup inventory. `TTY_CLASS` is not proof that `VSAB/TTY` exists. |

The October archive inventory contains `src/sources.src` and `src/termgroups.src` as well as `insert` copies. These are workflow artifacts. Their existence, archive location, timestamps or matching candidate bytes do not prove installation or that all relevant external anchors were captured. The archive review already found multiple release tags in the same archive; choose artifacts by verified role, not directory name alone.

## Evidence needed before an assembler

1. Identify and capture the actual installed-state export producer and the runtime/backend it addresses. Retain its source hash, invocation shape, selected environment, export time and raw output. Establish whether it exports current state or can address an identified frozen state.
2. Establish source/version identity from real output. Preserve the original API response or documented exporter fields rather than rely only on the wrapper's reconstructed VSAB. Confirm coverage of all NCI-family sources and every external ranking anchor required by the release plan.
3. Establish SRC/RPT source-root identity from real export code and a sample. The evidence must identify the source abbreviation, exact root atom type/code and the **source atom ID**, including any required mapping from backend-local atom identity. The saved hierarchy root is a different input.
4. Establish installed termgroup identity and scope from a working producer. A supported export must distinguish an installed `VSAB/TTY` from a generic TTY definition and from a proposed `termgroups.src` row. Capture the complete required scope, including external ranking targets.
5. Review source-family classification and the explicit active `replacement_sources` for the chosen transition. An arbitrary suffix, adjacent folder or catalog membership cannot decide these roles. Retained historical metadata must be distinguishable from the active replacement set.
6. Establish consistency across exports. Retain a shared frozen-state identity or a supported consistent-capture mechanism. Equal timestamps and manually copied identifiers alone cannot prove one coherent database state.

Only after those meanings are supported should the assembler translate existing trustworthy exports to `ncimeta-installed-state-v1`, bind all raw evidence hashes, reject incomplete/ambiguous captures, and pass the existing preflight. Its provenance checks cannot by themselves prove the truth of a manually asserted completeness claim.

## Narrow read-only server collection

Captured `ENV/etc/env.prop:21–24` resolves the operational locations. The first collection should inspect filenames and script bytes only:

- `/local/content/MEME/MEME5/inv/INV_OLD/bin/dump_src_info.pl`: the exact producer named by the NCIt runbook. Preserve its imports/supporting modules after inspecting the file; do not execute it merely to discover its behavior.
- `/local/content/MEME/MEME5/inv/INV/bin/dump_src_info.pl`: confirm whether an alternative exists now; this file is absent from the captured repository.
- `/local/content/MEME/MEME5/ncim/bin/dump_table.pl`: inspect the exporter wrapper/backend selection if present. Its name and use in old insertion code do not establish a modern query contract.
- A bounded filename listing of `/local/content/MEME/MEME5/ncim/bin` and the two inversion `bin` directories for `*src*`, `*source*`, `*termgroup*`, `*metadata*`, `*root*`, `*export*` and `*dump*`. Select further script reads from that listing.
- Existing preserved raw exports or capture logs named by those producers. Request concrete paths after reading the producer; avoid assuming that a prior source folder contains installed-state evidence.

Do not collect credential configuration contents or invoke API authentication for this discovery. No new SQL is proposed. If a current-state read-only export is later approved and supported by the captured producer, retain it as the state for that run; it must not be described as reconstructed October state.

## Outstanding semantic decisions

The capture work does not resolve the `CTCAE 6.0` representation choice. Nor does the missing `CELLOSAURUS_2026_10D/SY` row in October preparation metadata establish whether that target existed in the insertion database. Both remain explicit review findings. A genuine installed-termgroup export can answer the latter existence question for its identified state; changing the ranking still requires reviewed policy.
