# NCIt source plans and generated metadata

The source-plan profile generates `sources.src`, `termgroups.src`, the compatibility configuration, and explicit SRC-root/termgroup input files from the common configuration, a pinned metadata catalog and a reviewed release plan. All executable code comes from Git. No previous release executable or completed core output is copied into a candidate.

The common field is still `inputs.source_plan`. Its artifact contains the [typed NCIt source plan](nci-source-plan.schema.json); [October's example](configuration-examples/nci-source-plan-october-2026.json) records its explicit August replacement, one new subsource and two new termgroups. The metadata catalog is selected through `inputs.reference_ncimeta`, with its exact Git model identity bound in the lock. It is a structured, reviewed representation of captured preparation metadata, not a reconstructed historical database or live installed-root inventory.

## Release decisions

Every plan explicitly provides `new_subsources`, `new_termgroups`, `property_updates` and `historical_exceptions`, including empty arrays/objects when applicable. An established subsource stays in generated versioned metadata without emitting its root again. Catalog membership describes known representation; the reviewer determines which roots/termgroups are new to the selected NCImeta transition. A newly accepted definition should be retained in the versioned catalog for subsequent releases; this is a reviewed data/policy change, not an executable copy-forward step.

A new subsource specifies complete named metadata fields, publisher aliases, its insertion position and root preferred/short names. A new termgroup specifies the six actual loader fields, insertion position and native term types. Only reviewed new term-type mappings may extend the existing compatibility policy; conflicting existing mappings are rejected. Planned token bindings handle long source names and term types without adding regular-expression branches to Perl.

`low_source` and `low_termgroup` are explicit ranking decisions. They can refer to another member of the current batch. Established-source defaults use the explicitly selected replacement release; no previous calendar month is inferred. Validation rejects duplicate identities/decisions, missing metadata, bad flags, inconsistent source/TTY identities, missing anchors, unknown/cyclic ranking targets, a new definition referring to its nonexistent prior identity, and an ID range too small even for required SRC atoms. Common historical bounds are not production ID reservations.

The producer reads the generated ordered root list. Each new subsource emits the same RPT, RAB, SSN, relationship, two merges and semantic-type attribute as the characterized October producer, at the same point in allocation. Empty lists emit none. New subsource/termgroup decisions require no script edits or comment toggles.

## Discovery and immutable preparation

Before publishing a candidate or invoking Perl preparation, scan all five pinned native exports. Reject changed input identities, unknown source/term-type pairs, missing source metadata/mappings, new properties/relationship roles, changed representation labels, malformed termgroup qualifiers and unknown Maps_To meanings. New declarations require a reviewed plan/catalog update; discovery does not invent policy.

The source-plan candidate is seeded with only the five publisher files. Metadata is rendered from the locked model/plan, rather than extracted from archived `src` metadata. In the October compatibility case, the archived metadata hashes are independent expected results checked after generation. Generated files are read-only, rehashed before/after execution and retained with binding/discovery receipts. The original `generated-configuration` case stays pinned to its original engine and remains executable.

## Two historical findings kept explicit

The October scan found `CTCAE 6.0` in 4,111 native term records with no corresponding captured `vsab` mapping. Its existing output behavior is preserved for this compatibility exercise; no corrected mapping or complete representation is claimed.

The preserved October BLOODPAC/SY low-termgroup value is `CELLOSAURUS_2026_10D/SY`, which is absent from that metadata bundle. Existence in the insertion database has not been established. This value is preserved as an expected historical input choice, not silently declared a verified database reference.

Both findings are explicit exceptions bound to the exact version and all five native file hashes. Changed versions or input bundles cannot inherit them. They remain in the preparation/result receipts and do not confer production eligibility. Future release preparation requires reviewed representation and validated ranking targets. No semantic correction to either finding is part of this migration.

## Verification

Run `python3 -B tools/check_nci_source_plan.py` for independent golden metadata hashes, every effective legacy property, actual old/new Perl output equivalence, no-additions behavior, an established subsource without repeated roots, a long new subsource, a new term type and negative discovery/plan cases. Use the isolated runner environment for `tools/check_inversion_request.py`. Historical core replay uses the same common resolver, preservation, runtime lock, dev worker and official per-output references described in [the common interface](common-interface.md).

General new-release case registration, publisher acquisition, a fresh NCImeta metadata snapshot/installed-root inventory, source removals, production allocation, legacy database QA, insertion and production eligibility remain separately scoped. The versioned catalog and release-plan machinery do not infer those decisions from a prior folder or today's database.
